"""
AWS CloudFront Service
Handles SSL certificate management (ACM) and CloudFront distribution creation
for serving S3-hosted websites over HTTPS with custom domains.
"""

import time
from typing import Dict, Any, Optional, List

try:
    import boto3
    from botocore.exceptions import ClientError, WaiterError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

from src.utils.logger import get_logger
from src.utils.config import get_settings, Settings

logger = get_logger(__name__)


class AWSCloudFrontError(Exception):
    """Base exception for AWS CloudFront service errors"""
    pass


# Backwards-compatible alias
AWSCDNError = AWSCloudFrontError


class AWSCloudFrontService:
    """
    AWS CloudFront & ACM Service.

    Handles:
    - SSL/TLS certificate provisioning via ACM (us-east-1)
    - DNS-based certificate validation via Route53
    - CloudFront distribution creation with HTTPS enforcement
    - Polling until distributions are fully deployed
    """

    def __init__(self, config: Optional[Settings] = None):
        """
        Initialize the CloudFront service.

        Args:
            config: Optional Settings object. Defaults to get_settings().
        """
        if not AWS_AVAILABLE:
            raise ImportError("boto3 is required. Install with: pip install boto3")

        self.config = config or get_settings()

        # CloudFront and ACM must be in us-east-1 (global services)
        shared_kwargs = {
            "aws_access_key_id": self.config.aws_access_key_id,
            "aws_secret_access_key": self.config.aws_secret_access_key,
            "region_name": "us-east-1",
        }

        self.cloudfront_client = boto3.client("cloudfront", **shared_kwargs)
        self.acm_client = boto3.client("acm", **shared_kwargs)

        logger.info("AWSCloudFrontService initialized")

    # ------------------------------------------------------------------ #
    #  ACM — SSL Certificates                                              #
    # ------------------------------------------------------------------ #

    def request_ssl_certificate(self, domain: str, include_www: bool = True) -> str:
        """
        Request a public SSL/TLS certificate from AWS Certificate Manager (ACM).

        The certificate uses DNS validation — you must call `add_acm_dns_records`
        followed by `wait_for_certificate` to complete the issuance process.

        Args:
            domain:       Apex domain, e.g. "my-app.com"
            include_www:  Also cover "www.my-app.com" (True by default)
        """
        logger.info(f"Requesting SSL certificate for: {domain}")

        subject_alt_names = [f"www.{domain}"] if include_www else []

        try:
            kwargs: Dict[str, Any] = {
                "DomainName": domain,
                "ValidationMethod": "DNS",
                "IdempotencyToken": domain.replace(".", "-")[:32],
            }
            if subject_alt_names:
                kwargs["SubjectAlternativeNames"] = subject_alt_names

            response = self.acm_client.request_certificate(**kwargs)
            cert_arn = response["CertificateArn"]

            logger.info(f"✅ Certificate requested: {cert_arn}")
            logger.info("⏳ Next: get acm validation records and call add_acm_dns_records()")
            return cert_arn

        except ClientError as e:
            logger.error(f"ACM request failed: {e}")
            raise AWSCloudFrontError(f"Certificate request failed: {e}")

    def get_acm_validation_records(
        self, cert_arn: str, timeout_seconds: int = 60
    ) -> List[Dict[str, str]]:
        """
        Retrieve the DNS CNAME records that ACM needs for domain validation.

        ACM may take a few seconds after certificate creation before these
        records are available; this method polls until they appear.

        Args:
            cert_arn:        Certificate ARN from request_ssl_certificate()
            timeout_seconds: Max wait time before raising (default 60 s)

        Returns:
            List of dicts: [{"name": "...", "value": "..."}]
        """
        logger.info(f"Fetching ACM validation records for {cert_arn}")
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                cert = self.acm_client.describe_certificate(CertificateArn=cert_arn)
                domain_validations = (
                    cert["Certificate"].get("DomainValidationOptions", [])
                )
                records = []
                for dv in domain_validations:
                    rr = dv.get("ResourceRecord")
                    if rr:
                        records.append({"name": rr["Name"], "value": rr["Value"]})

                if records:
                    logger.info(f"✅ Got {len(records)} validation record(s)")
                    logger.info("⏳ Next: call add_acm_dns_records() then wait_for_certificate()")
                    return records

            except ClientError as e:
                raise AWSCloudFrontError(f"describe_certificate failed: {e}")

            logger.debug("Validation records not ready yet, retrying in 5 s…")
            time.sleep(5)

        raise AWSCloudFrontError(
            f"ACM validation records not available after {timeout_seconds}s"
        )

    def wait_for_certificate(
        self, cert_arn: str, timeout_minutes: int = 30
    ) -> None:
        """
        Block until the ACM certificate status becomes ISSUED.

        DNS validation must already be in place (CNAME records written to
        Route53) before calling this.

        Args:
            cert_arn:        Certificate ARN
            timeout_minutes: Max wait time (default 30 min)
        """
        logger.info(f"Waiting for certificate to be issued: {cert_arn}")
        deadline = time.time() + timeout_minutes * 60
        poll_interval = 30

        while time.time() < deadline:
            try:
                cert = self.acm_client.describe_certificate(CertificateArn=cert_arn)
                status = cert["Certificate"]["Status"]
                logger.info(f"  Certificate status: {status}")

                if status == "ISSUED":
                    logger.info("✅ Certificate is ISSUED")
                    return
                if status in ("FAILED", "REVOKED", "EXPIRED"):
                    raise AWSCloudFrontError(
                        f"Certificate entered terminal state: {status}"
                    )

            except ClientError as e:
                raise AWSCloudFrontError(f"describe_certificate failed: {e}")

            logger.info(f"  Waiting {poll_interval}s before next check…")
            time.sleep(poll_interval)

        raise AWSCloudFrontError(
            f"Certificate not issued within {timeout_minutes} minutes"
        )

    # ------------------------------------------------------------------ #
    #  CloudFront — Distributions                                          #
    # ------------------------------------------------------------------ #

    def create_s3_distribution(
        self,
        bucket_name: str,
        domain_name: str,
        certificate_arn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a CloudFront distribution backed by an S3 static-website origin.

        When ``certificate_arn`` is provided the distribution enforces HTTPS
        (HTTP → HTTPS redirect).  Without it, the distribution allows plain
        HTTP only (useful for testing before the certificate is ready).

        Args:
            bucket_name:       S3 bucket name (must have static-website hosting enabled)
            domain_name:       Custom domain for the CNAME Alias, e.g. "my-app.com"
            certificate_arn:   ACM certificate ARN (us-east-1). If omitted, HTTPS is
                               not enforced.

        Returns:
            Dict with keys:
              - distribution_id    (str)
              - distribution_domain (str, e.g. "d123.cloudfront.net")
              - status             (str, initially "InProgress")
              - arn                (str)

        Raises:
            AWSCloudFrontError: On CloudFront API failure
        """
        logger.info(
            f"Creating CloudFront distribution: bucket={bucket_name}, "
            f"domain={domain_name}, ssl={'yes' if certificate_arn else 'no'}"
        )

        origin_id = f"S3-{bucket_name}"
        s3_website_endpoint = (
            f"{bucket_name}.s3-website-{self.config.aws_region}.amazonaws.com"
        )

        viewer_protocol_policy = (
            "redirect-to-https" if certificate_arn else "allow-all"
        )

        viewer_certificate: Dict[str, Any]
        if certificate_arn:
            viewer_certificate = {
                "ACMCertificateArn": certificate_arn,
                "SSLSupportMethod": "sni-only",
                "MinimumProtocolVersion": "TLSv1.2_2021",
            }
        else:
            viewer_certificate = {"CloudFrontDefaultCertificate": True}

        distribution_config: Dict[str, Any] = {
            "CallerReference": str(time.time()),
            "Aliases": {"Quantity": 1, "Items": [domain_name]},
            "DefaultRootObject": "index.html",
            "Origins": {
                "Quantity": 1,
                "Items": [
                    {
                        "Id": origin_id,
                        "DomainName": s3_website_endpoint,
                        "CustomOriginConfig": {
                            "HTTPPort": 80,
                            "HTTPSPort": 443,
                            "OriginProtocolPolicy": "http-only",
                            "OriginSslProtocols": {
                                "Quantity": 3,
                                "Items": ["TLSv1", "TLSv1.1", "TLSv1.2"],
                            },
                        },
                    }
                ],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": origin_id,
                "ForwardedValues": {
                    "QueryString": False,
                    "Cookies": {"Forward": "none"},
                },
                "TrustedSigners": {"Enabled": False, "Quantity": 0},
                "ViewerProtocolPolicy": viewer_protocol_policy,
                "MinTTL": 0,
            },
            "CacheBehaviors": {"Quantity": 0},
            "CustomErrorResponses": {
                "Quantity": 2,
                "Items": [
                    {
                        "ErrorCode": 403,
                        "ResponsePagePath": "/404.html",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 10,
                    },
                    {
                        "ErrorCode": 404,
                        "ResponsePagePath": "/404.html",
                        "ResponseCode": "404",
                        "ErrorCachingMinTTL": 10,
                    },
                ],
            },
            "Comment": f"Created by AI-Website for {domain_name}",
            "ViewerCertificate": viewer_certificate,
            "Enabled": True,
        }

        try:
            response = self.cloudfront_client.create_distribution(
                DistributionConfig=distribution_config
            )
            dist = response["Distribution"]
            logger.info(f"✅ Distribution created: {dist['Id']}")

            return {
                "distribution_id": dist["Id"],
                "distribution_domain": dist["DomainName"],
                "status": dist["Status"],
                "arn": dist["ARN"],
            }

        except ClientError as e:
            logger.error(f"CloudFront creation failed: {e}")
            raise AWSCloudFrontError(f"CloudFront creation failed: {e}")

    def wait_for_distribution(
        self, distribution_id: str, timeout_minutes: int = 30
    ) -> None:
        """
        Block until a CloudFront distribution status becomes "Deployed".

        New distributions typically take 15-20 minutes.

        Args:
            distribution_id: CloudFront distribution ID (e.g. "E1ABCXYZ")
            timeout_minutes: Max wait time (default 30 min)

        Raises:
            AWSCloudFrontError: If not deployed within timeout
        """
        logger.info(f"⏳ Waiting for distribution {distribution_id} to deploy…")
        deadline = time.time() + timeout_minutes * 60
        poll_interval = 60  # CloudFront deploys in minutes, no need to hammer

        while time.time() < deadline:
            try:
                resp = self.cloudfront_client.get_distribution(Id=distribution_id)
                status = resp["Distribution"]["Status"]
                logger.info(f"  Distribution status: {status}")

                if status == "Deployed":
                    logger.info("✅ Distribution is Deployed")
                    return

            except ClientError as e:
                raise AWSCloudFrontError(f"get_distribution failed: {e}")

            logger.info(f"  Waiting {poll_interval}s before next check…")
            time.sleep(poll_interval)

        raise AWSCloudFrontError(
            f"Distribution not deployed within {timeout_minutes} minutes"
        )


# Backwards-compatible alias so existing code using AWSCDNService keeps working
AWSCDNService = AWSCloudFrontService
