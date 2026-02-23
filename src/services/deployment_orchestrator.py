"""
Deployment Orchestrator
Combines DeploymentService, AWSCloudFrontService, and AWSDomainService
into a single end-to-end pipeline that takes a Next.js app from source
to a live HTTPS site with a custom domain.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from src.utils.logger import get_logger
from src.utils.config import get_settings, Settings
from src.services.deployment_service import DeploymentService
from src.services.aws_cdn_service import AWSCloudFrontService
from src.services.aws_domain_service import AWSDomainService

logger = get_logger(__name__)


class OrchestratorError(Exception):
    """Raised when any step of the deployment pipeline fails"""
    pass


class DeploymentOrchestrator:
    """
    End-to-end deployment pipeline orchestrator.

    Runs all steps required to publish a Next.js build as a live HTTPS
    website on AWS in the correct order:

    1.  (Optional) Install dependencies  — ``pnpm install``
    2.  Build the project                — ``pnpm build``
    3.  Upload build to S3               — static-website hosting
    4.  Request SSL certificate          — ACM (us-east-1, DNS validation)
    5.  Write ACM validation DNS records — Route53 CNAME records
    6.  Wait for certificate ISSUED      — polls ACM (up to 30 min)
    7.  Create CloudFront distribution   — HTTPS enforced with ACM cert
    8.  Point Route53 to CloudFront      — Alias A + www CNAME records
    9.  Wait for distribution to deploy  — polls CloudFront (up to 30 min)
    10. Return live URL                  — ``"https://<domain>"``
    """

    def __init__(self, config: Optional[Settings] = None):
        """
        Initialize the orchestrator with a shared configuration.

        Args:
            config: Optional Settings object. Defaults to get_settings().
        """
        self.config = config or get_settings()
        self.cf_service = AWSCloudFrontService(config=self.config)
        self.dns_service = AWSDomainService(config=self.config)

    def deploy_full(
        self,
        app_dir: Path,
        bucket_name: str,
        domain: str,
        install: bool = False,
        build_command: str = "pnpm build",
        contact_info: Optional[Dict[str, Any]] = None,
        duration_years: int = 1,
        cert_timeout_minutes: int = 30,
        distribution_timeout_minutes: int = 30,
    ) -> Dict[str, Any]:
        """
        Run the complete deployment pipeline (up to 11 steps).

        Args:
            app_dir:                        Path to the Next.js application directory
            bucket_name:                    S3 bucket name (must already exist and have
                                            static-website hosting enabled)
            domain:                         Apex domain, e.g. "my-app.com"
            install:                        Run ``pnpm install`` before building
                                            (default False)
            build_command:                  Override the build command (default
                                            ``"pnpm build"``)
            contact_info:                   AWSContactInfo dict for domain registration.
                                            If provided, the domain will be registered
                                            before building. Omit if already registered.
            duration_years:                 Domain registration period in years (default 1).
                                            Only used when contact_info is provided.
            cert_timeout_minutes:           Max wait time for certificate issuance
                                            (default 30 min)
            distribution_timeout_minutes:   Max wait time for CloudFront to become
                                            Deployed (default 30 min)

        Returns:
            Dict with keys:
              - url                  (str, e.g. "https://my-app.com")
              - distribution_id      (str)
              - distribution_domain  (str)
              - certificate_arn      (str)

        Raises:
            OrchestratorError: If any pipeline step fails
        """
        logger.info(f"🚀 Starting full deployment pipeline for {domain}")
        logger.info(f"   App:    {app_dir}")
        logger.info(f"   Bucket: {bucket_name}")

        deploy_svc = DeploymentService(Path(app_dir), config=self.config)

        try:
            # ── Step 1: Install dependencies (optional) ──────────────────────
            if install:
                logger.info("── Step 1/10: Installing dependencies")
                deploy_svc.install_dependencies()
            else:
                logger.info("── Step 1/10: Skipping install (pass install=True to enable)")

            # ── Step 2: Register domain (optional) ───────────────────────────
            if contact_info:
                logger.info(f"── Step 2/10: Registering domain {domain}")
                reg_result = self.dns_service.register_domain(
                    domain=domain,
                    contact_info=contact_info,
                    duration_years=duration_years,
                )
                logger.info(f"  Registration submitted — operation_id: {reg_result.get('operation_id')}")
                logger.info("  ⚠️ Registration may take several minutes; continuing pipeline.")
            else:
                logger.info("── Step 2/10: Skipping registration (pass contact_info= to register)")

            # ── Step 3: Build ─────────────────────────────────────────────────
            logger.info("── Step 3/10: Building project")
            deploy_svc.run_build(build_command=build_command)

            # ── Step 4: Upload to S3 ──────────────────────────────────────────
            logger.info("── Step 4/10: Uploading build to S3")
            deploy_svc.deploy_s3(bucket_name=bucket_name, make_public=True)

            # ── Step 5: Request SSL certificate ───────────────────────────────
            logger.info("── Step 5/10: Requesting SSL certificate (ACM)")
            cert_arn = self.cf_service.request_ssl_certificate(
                domain=domain, include_www=True
            )

            # ── Step 6: Write DNS validation records ──────────────────────────
            logger.info("── Step 6/10: Writing ACM DNS validation records")
            validation_records = self.cf_service.get_acm_validation_records(cert_arn)
            self.dns_service.add_acm_dns_records(
                domain=domain, validation_records=validation_records
            )

            # ── Step 7: Wait for certificate ──────────────────────────────────
            logger.info("── Step 7/10: Waiting for certificate to be ISSUED")
            self.cf_service.wait_for_certificate(
                cert_arn=cert_arn, timeout_minutes=cert_timeout_minutes
            )

            # ── Step 8: Create CloudFront distribution ────────────────────────
            logger.info("── Step 8/10: Creating CloudFront distribution (HTTPS)")
            distribution = self.cf_service.create_s3_distribution(
                bucket_name=bucket_name,
                domain_name=domain,
                certificate_arn=cert_arn,
            )
            dist_id = distribution["distribution_id"]
            dist_domain = distribution["distribution_domain"]

            # ── Step 9: Point Route53 to CloudFront ───────────────────────────
            logger.info("── Step 9/10: Pointing Route53 DNS to CloudFront")
            self.dns_service.setup_cloudfront_dns(
                domain=domain, distribution_domain=dist_domain
            )

            # ── Step 10: Wait for distribution to deploy ──────────────────────
            logger.info("── Step 10/10: Waiting for CloudFront distribution to deploy")
            self.cf_service.wait_for_distribution(
                distribution_id=dist_id,
                timeout_minutes=distribution_timeout_minutes,
            )

            live_url = f"https://{domain}"
            logger.info(f"🎉 Your site is live at {live_url}")

            return {
                "url": live_url,
                "distribution_id": dist_id,
                "distribution_domain": dist_domain,
                "certificate_arn": cert_arn,
            }

        except Exception as exc:
            logger.error(f"❌ Deployment pipeline failed: {exc}")
            raise OrchestratorError(str(exc)) from exc
