"""
Tests for the full deployment pipeline methods.
All AWS API calls are mocked — no real credentials or AWS resources needed.

Run:
    python -m pytest tests/test_deployment_pipeline.py -v
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

DOMAIN = "my-app.com"
BUCKET = "my-website-bucket"
CERT_ARN = "arn:aws:acm:us-east-1:123456789012:certificate/abc-123"
DIST_ID = "E1ABCXYZ"
DIST_DOMAIN = "d123.cloudfront.net"

CONTACT_INFO = {
    "FirstName": "Jane",
    "LastName": "Doe",
    "Email": "jane@example.com",
    "PhoneNumber": "+1.5551234567",
    "AddressLine1": "123 Main St",
    "City": "Austin",
    "State": "TX",
    "CountryCode": "US",
    "ZipCode": "78701",
}


def _make_client_error(code: str = "ValidationException") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "Mocked AWS error"}},
        "TestOperation",
    )


def _mock_settings():
    """Return a minimal mock Settings object."""
    s = MagicMock()
    s.aws_access_key_id = "AKIATEST"
    s.aws_secret_access_key = "testsecret"
    s.aws_region = "us-east-1"
    return s


# ===========================================================================
# 1. DeploymentService — install_dependencies
# ===========================================================================

class TestInstallDependencies:

    def _make_service(self, tmp_path):
        from src.services.deployment_service import DeploymentService
        return DeploymentService(tmp_path, config=_mock_settings())

    def test_install_runs_default_command(self, tmp_path):
        """install_dependencies should run 'pnpm install' by default."""
        svc = self._make_service(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            svc.install_dependencies()
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "pnpm" in args and "install" in args # Checking if the command run includs 'pnpm' and 'install'

    def test_install_uses_custom_command(self, tmp_path):
        """install_dependencies should use a custom command when provided."""
        svc = self._make_service(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            svc.install_dependencies("npm ci")
            args = mock_run.call_args[0][0]
            assert "npm" in args and "ci" in args

    def test_install_raises_on_failure(self, tmp_path):
        """install_dependencies should raise when the subprocess fails."""
        svc = self._make_service(tmp_path)
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "pnpm install")):
            with pytest.raises(Exception):
                svc.install_dependencies()


# ===========================================================================
# 2. AWSDomainService — register_domain
# ===========================================================================

class TestRegisterDomain:

    @patch("boto3.client")
    def test_register_domain_success(self, mock_boto):
        """register_domain should call Route53Domains and return operation_id."""
        from src.services.aws_domain_service import AWSDomainService

        mock_client = MagicMock()
        mock_client.register_domain.return_value = {"OperationId": "op-123-abc"}
        mock_boto.return_value = mock_client

        svc = AWSDomainService(config=_mock_settings())
        result = svc.register_domain(DOMAIN, CONTACT_INFO)

        assert result["operation_id"] == "op-123-abc"
        mock_client.register_domain.assert_called_once()

    @patch("boto3.client")
    def test_register_domain_raises_on_aws_error(self, mock_boto):
        """register_domain should raise AWSDomainError when ACM returns an error."""
        from src.services.aws_domain_service import AWSDomainService, AWSDomainError

        mock_client = MagicMock()
        mock_client.register_domain.side_effect = _make_client_error("DomainLimitExceeded")
        mock_boto.return_value = mock_client

        svc = AWSDomainService(config=_mock_settings())
        with pytest.raises(AWSDomainError):
            svc.register_domain(DOMAIN, CONTACT_INFO)


# ===========================================================================
# 3. DeploymentService — build and upload to S3
# ===========================================================================

class TestBuildAndUpload:

    def _make_service(self, tmp_path):
        from src.services.deployment_service import DeploymentService
        return DeploymentService(tmp_path, config=_mock_settings())

    def test_run_build_calls_subprocess(self, tmp_path):
        """run_build should invoke the build command via subprocess."""
        svc = self._make_service(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            svc.run_build()
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "pnpm" in cmd and "build" in cmd

    def test_deploy_s3_uploads_files(self, tmp_path):
        """deploy_s3 should upload files from the build output directory to S3."""
        from src.services.deployment_service import DeploymentService

        # Create a fake out/ directory with two files
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "index.html").write_text("<html/>")
        (out_dir / "about.html").write_text("<html/>")

        svc = DeploymentService(tmp_path, config=_mock_settings())

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.return_value = mock_s3

            result = svc.deploy_s3(bucket_name=BUCKET, make_public=True)

        assert result["bucket"] == BUCKET
        assert result["file_count"] == 2 # created 2 files in out directory
        assert mock_s3.upload_file.call_count == 2 # copied 2 files to s3

    def test_deploy_s3_raises_on_client_error(self, tmp_path):
        """deploy_s3 should raise DeploymentError when S3 upload fails."""
        from src.services.deployment_service import DeploymentService, DeploymentError

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "index.html").write_text("<html/>")

        svc = DeploymentService(tmp_path, config=_mock_settings())

        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.upload_file.side_effect = _make_client_error("NoSuchBucket")
            mock_boto.return_value = mock_s3

            with pytest.raises(DeploymentError):
                svc.deploy_s3(bucket_name=BUCKET)


# ===========================================================================
# 4. AWSCloudFrontService — request_ssl_certificate
# ===========================================================================

class TestRequestSSLCertificate:

    @patch("boto3.client")
    def test_request_returns_cert_arn(self, mock_boto):
        """request_ssl_certificate should return the certificate ARN string."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_acm = MagicMock()
        mock_acm.request_certificate.return_value = {"CertificateArn": CERT_ARN}
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        result = svc.request_ssl_certificate(DOMAIN, include_www=True)

        assert result == CERT_ARN
        call_kwargs = mock_acm.request_certificate.call_args[1]
        assert call_kwargs["DomainName"] == DOMAIN
        assert call_kwargs["ValidationMethod"] == "DNS"
        assert f"www.{DOMAIN}" in call_kwargs.get("SubjectAlternativeNames", [])

    @patch("boto3.client")
    def test_request_without_www(self, mock_boto):
        """include_www=False should not add www subdomain as a SAN."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_acm = MagicMock()
        mock_acm.request_certificate.return_value = {"CertificateArn": CERT_ARN}
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        svc.request_ssl_certificate(DOMAIN, include_www=False)

        call_kwargs = mock_acm.request_certificate.call_args[1]
        assert "SubjectAlternativeNames" not in call_kwargs

    @patch("boto3.client")
    def test_request_raises_on_acm_error(self, mock_boto):
        """request_ssl_certificate should raise AWSCloudFrontError on ACM failure."""
        from src.services.aws_cdn_service import AWSCloudFrontService, AWSCloudFrontError

        mock_acm = MagicMock()
        mock_acm.request_certificate.side_effect = _make_client_error("LimitExceededException")
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        with pytest.raises(AWSCloudFrontError):
            svc.request_ssl_certificate(DOMAIN)


# ===========================================================================
# 5. AWSCloudFrontService — get_acm_validation_records  &
#    AWSDomainService  — add_acm_dns_records
# ===========================================================================

class TestCertificateValidation:

    @patch("boto3.client")
    def test_get_validation_records_returns_cname_list(self, mock_boto):
        """get_acm_validation_records should return list of name/value dicts."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_acm = MagicMock()
        mock_acm.describe_certificate.return_value = {
            "Certificate": {
                "DomainValidationOptions": [
                    {
                        "DomainName": DOMAIN,
                        "ResourceRecord": {
                            "Name": "_abc._validations.my-app.com.",
                            "Type": "CNAME",
                            "Value": "_xyz.acm-validations.aws.",
                        },
                    }
                ]
            }
        }
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        records = svc.get_acm_validation_records(CERT_ARN, timeout_seconds=5)

        assert len(records) == 1
        assert "name" in records[0]
        assert "value" in records[0]

    @patch("boto3.client")
    def test_get_validation_records_times_out(self, mock_boto):
        """get_acm_validation_records should raise if records never appear."""
        from src.services.aws_cdn_service import AWSCloudFrontService, AWSCloudFrontError

        mock_acm = MagicMock()
        # No ResourceRecord key — simulates not-yet-ready state
        mock_acm.describe_certificate.return_value = {
            "Certificate": {"DomainValidationOptions": [{"DomainName": DOMAIN}]}
        }
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        with pytest.raises(AWSCloudFrontError, match="not available"):
            svc.get_acm_validation_records(CERT_ARN, timeout_seconds=1)

    @patch("boto3.client")
    def test_add_acm_dns_records_writes_cnames(self, mock_boto):
        """add_acm_dns_records should upsert CNAME records in Route53."""
        from src.services.aws_domain_service import AWSDomainService

        mock_r53 = MagicMock()
        mock_r53.list_hosted_zones_by_name.return_value = {
            "HostedZones": [{"Name": f"{DOMAIN}.", "Id": "/hostedzone/Z123"}]
        }
        mock_r53.change_resource_record_sets.return_value = {
            "ChangeInfo": {"Id": "/change/C123"}
        }
        mock_boto.return_value = mock_r53

        records = [{"name": "_abc.my-app.com.", "value": "_xyz.acm-validations.aws."}]

        svc = AWSDomainService(config=_mock_settings())
        result = svc.add_acm_dns_records(DOMAIN, records)

        assert result["status"] == "success"
        mock_r53.change_resource_record_sets.assert_called_once()
        changes = mock_r53.change_resource_record_sets.call_args[1]["ChangeBatch"]["Changes"]
        assert changes[0]["ResourceRecordSet"]["Type"] == "CNAME"


# ===========================================================================
# 6. AWSCloudFrontService — wait_for_certificate
# ===========================================================================

class TestWaitForCertificate:

    @patch("boto3.client")
    def test_wait_returns_when_issued(self, mock_boto):
        """wait_for_certificate should return without error when cert is ISSUED."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_acm = MagicMock()
        mock_acm.describe_certificate.return_value = {
            "Certificate": {"Status": "ISSUED"}
        }
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        # Should not raise
        with patch("time.sleep"):
            svc.wait_for_certificate(CERT_ARN, timeout_minutes=1)

    @patch("boto3.client")
    def test_wait_raises_on_failed_status(self, mock_boto):
        """wait_for_certificate should raise when cert enters terminal FAILED state."""
        from src.services.aws_cdn_service import AWSCloudFrontService, AWSCloudFrontError

        mock_acm = MagicMock()
        mock_acm.describe_certificate.return_value = {
            "Certificate": {"Status": "FAILED"}
        }
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        with pytest.raises(AWSCloudFrontError, match="FAILED"):
            with patch("time.sleep"):
                svc.wait_for_certificate(CERT_ARN, timeout_minutes=1)

    @patch("boto3.client")
    def test_wait_raises_on_timeout(self, mock_boto):
        """wait_for_certificate should raise AWSCloudFrontError on timeout."""
        from src.services.aws_cdn_service import AWSCloudFrontService, AWSCloudFrontError
        import time

        mock_acm = MagicMock()
        mock_acm.describe_certificate.return_value = {
            "Certificate": {"Status": "PENDING_VALIDATION"}
        }
        mock_boto.return_value = mock_acm

        svc = AWSCloudFrontService(config=_mock_settings())
        # Use a near-zero timeout and mock sleep to skip actual waiting
        with patch("time.sleep"):
            with patch("time.time", side_effect=[0, 0, 9999]):  # instant timeout
                with pytest.raises(AWSCloudFrontError, match="not issued"):
                    svc.wait_for_certificate(CERT_ARN, timeout_minutes=0)


# ===========================================================================
# 7. AWSCloudFrontService — create_s3_distribution
# ===========================================================================

class TestCreateS3Distribution:

    @patch("boto3.client")
    def test_create_with_https(self, mock_boto):
        """create_s3_distribution with cert_arn should set redirect-to-https."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_cf = MagicMock()
        mock_cf.create_distribution.return_value = {
            "Distribution": {
                "Id": DIST_ID,
                "DomainName": DIST_DOMAIN,
                "Status": "InProgress",
                "ARN": "arn:aws:cloudfront::123:distribution/E1",
            }
        }
        mock_boto.return_value = mock_cf

        svc = AWSCloudFrontService(config=_mock_settings())
        result = svc.create_s3_distribution(BUCKET, DOMAIN, certificate_arn=CERT_ARN)

        assert result["distribution_id"] == DIST_ID
        assert result["distribution_domain"] == DIST_DOMAIN

        config_sent = mock_cf.create_distribution.call_args[1]["DistributionConfig"]
        assert config_sent["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "redirect-to-https"
        assert "ACMCertificateArn" in config_sent["ViewerCertificate"]

    @patch("boto3.client")
    def test_create_without_cert_uses_http(self, mock_boto):
        """create_s3_distribution without cert_arn should allow HTTP traffic."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_cf = MagicMock()
        mock_cf.create_distribution.return_value = {
            "Distribution": {
                "Id": DIST_ID,
                "DomainName": DIST_DOMAIN,
                "Status": "InProgress",
                "ARN": "arn:aws:cloudfront::123:distribution/E1",
            }
        }
        mock_boto.return_value = mock_cf

        svc = AWSCloudFrontService(config=_mock_settings())
        svc.create_s3_distribution(BUCKET, DOMAIN, certificate_arn=None)

        config_sent = mock_cf.create_distribution.call_args[1]["DistributionConfig"]
        assert config_sent["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "allow-all"
        assert config_sent["ViewerCertificate"].get("CloudFrontDefaultCertificate") is True

    @patch("boto3.client")
    def test_create_raises_on_cloudfront_error(self, mock_boto):
        """create_s3_distribution should raise AWSCloudFrontError on API failure."""
        from src.services.aws_cdn_service import AWSCloudFrontService, AWSCloudFrontError

        mock_cf = MagicMock()
        mock_cf.create_distribution.side_effect = _make_client_error("InvalidViewerCertificate")
        mock_boto.return_value = mock_cf

        svc = AWSCloudFrontService(config=_mock_settings())
        with pytest.raises(AWSCloudFrontError):
            svc.create_s3_distribution(BUCKET, DOMAIN, certificate_arn=CERT_ARN)


# ===========================================================================
# 8. AWSDomainService — setup_cloudfront_dns
# ===========================================================================

class TestSetupCloudfrontDns:

    @patch("boto3.client")
    def test_setup_creates_alias_and_cname(self, mock_boto):
        """setup_cloudfront_dns should upsert an Alias A record and www CNAME."""
        from src.services.aws_domain_service import AWSDomainService

        mock_r53 = MagicMock()
        mock_r53.list_hosted_zones_by_name.return_value = {
            "HostedZones": [{"Name": f"{DOMAIN}.", "Id": "/hostedzone/Z999"}]
        }
        mock_r53.change_resource_record_sets.return_value = {
            "ChangeInfo": {"Id": "/change/C999"}
        }
        mock_boto.return_value = mock_r53

        svc = AWSDomainService(config=_mock_settings())
        result = svc.setup_cloudfront_dns(DOMAIN, DIST_DOMAIN)

        assert result["status"] == "success"
        changes = mock_r53.change_resource_record_sets.call_args[1]["ChangeBatch"]["Changes"]
        record_types = {c["ResourceRecordSet"]["Type"] for c in changes}
        assert "A" in record_types       # Alias root domain
        assert "CNAME" in record_types   # www subdomain

    @patch("boto3.client")
    def test_setup_uses_cloudfront_hosted_zone_id(self, mock_boto):
        """The Alias target must use CloudFront's fixed Hosted Zone ID."""
        from src.services.aws_domain_service import AWSDomainService

        mock_r53 = MagicMock()
        mock_r53.list_hosted_zones_by_name.return_value = {
            "HostedZones": [{"Name": f"{DOMAIN}.", "Id": "/hostedzone/Z999"}]
        }
        mock_r53.change_resource_record_sets.return_value = {
            "ChangeInfo": {"Id": "/change/C999"}
        }
        mock_boto.return_value = mock_r53

        svc = AWSDomainService(config=_mock_settings())
        svc.setup_cloudfront_dns(DOMAIN, DIST_DOMAIN)

        changes = mock_r53.change_resource_record_sets.call_args[1]["ChangeBatch"]["Changes"]
        alias_record = next(c for c in changes if c["ResourceRecordSet"]["Type"] == "A")
        assert alias_record["ResourceRecordSet"]["AliasTarget"]["HostedZoneId"] == "Z2FDTNDATAQYW2"


# ===========================================================================
# 9. AWSCloudFrontService — wait_for_distribution
# ===========================================================================

class TestWaitForDistribution:

    @patch("boto3.client")
    def test_wait_returns_when_deployed(self, mock_boto):
        """wait_for_distribution should return when status is Deployed."""
        from src.services.aws_cdn_service import AWSCloudFrontService

        mock_cf = MagicMock()
        mock_cf.get_distribution.return_value = {
            "Distribution": {"Status": "Deployed"}
        }
        mock_boto.return_value = mock_cf

        svc = AWSCloudFrontService(config=_mock_settings())
        with patch("time.sleep"):
            svc.wait_for_distribution(DIST_ID, timeout_minutes=1)  # should not raise

    @patch("boto3.client")
    def test_wait_raises_on_timeout(self, mock_boto):
        """wait_for_distribution should raise AWSCloudFrontError on timeout."""
        from src.services.aws_cdn_service import AWSCloudFrontService, AWSCloudFrontError

        mock_cf = MagicMock()
        mock_cf.get_distribution.return_value = {
            "Distribution": {"Status": "InProgress"}
        }
        mock_boto.return_value = mock_cf

        svc = AWSCloudFrontService(config=_mock_settings())
        with patch("time.sleep"):
            with patch("time.time", side_effect=[0, 0, 9999]):
                with pytest.raises(AWSCloudFrontError, match="not deployed"):
                    svc.wait_for_distribution(DIST_ID, timeout_minutes=0)


# ===========================================================================
# 10. DeploymentOrchestrator — deploy_full (integration, all steps mocked)
# ===========================================================================

class TestDeployFull:

    def _make_orchestrator(self):
        from src.services.deployment_orchestrator import DeploymentOrchestrator
        return DeploymentOrchestrator(config=_mock_settings())

    def _patch_all_services(self, tmp_path):
        """Return a dict of patchers for every service call in the pipeline."""
        return {
            "DeploymentService": patch(
                "src.services.deployment_orchestrator.DeploymentService"
            ),
            "AWSCloudFrontService": patch(
                "src.services.deployment_orchestrator.AWSCloudFrontService"
            ),
            "AWSDomainService": patch(
                "src.services.deployment_orchestrator.AWSDomainService"
            ),
        }

    def test_deploy_full_happy_path(self, tmp_path):
        """deploy_full should sequence all steps and return a live URL."""
        patchers = self._patch_all_services(tmp_path)

        with patchers["DeploymentService"] as mock_ds_cls, \
             patchers["AWSCloudFrontService"] as mock_cf_cls, \
             patchers["AWSDomainService"] as mock_dns_cls:

            # Wire up mock return values
            mock_ds = MagicMock()
            mock_ds_cls.return_value = mock_ds

            mock_cf = MagicMock()
            mock_cf.request_ssl_certificate.return_value = CERT_ARN
            mock_cf.get_acm_validation_records.return_value = [
                {"name": "_abc.my-app.com.", "value": "_xyz.acm-validations.aws."}
            ]
            mock_cf.create_s3_distribution.return_value = {
                "distribution_id": DIST_ID,
                "distribution_domain": DIST_DOMAIN,
                "status": "InProgress",
                "arn": "arn:aws:cloudfront::123:distribution/E1",
            }
            mock_cf_cls.return_value = mock_cf

            mock_dns = MagicMock()
            mock_dns.add_acm_dns_records.return_value = {"status": "success", "change_id": "C1"}
            mock_dns.setup_cloudfront_dns.return_value = {"status": "success", "hosted_zone_id": "Z1", "change_id": "C2"}
            mock_dns_cls.return_value = mock_dns

            orch = self._make_orchestrator()
            result = orch.deploy_full(
                app_dir=tmp_path,
                bucket_name=BUCKET,
                domain=DOMAIN,
                install=False,
            )

        assert result["url"] == f"https://{DOMAIN}"
        assert result["distribution_id"] == DIST_ID
        assert result["certificate_arn"] == CERT_ARN

        # Verify correct step ordering
        mock_ds.run_build.assert_called_once()
        mock_ds.deploy_s3.assert_called_once()
        mock_cf.request_ssl_certificate.assert_called_once_with(domain=DOMAIN, include_www=True)
        mock_cf.get_acm_validation_records.assert_called_once_with(CERT_ARN)
        mock_dns.add_acm_dns_records.assert_called_once()
        mock_cf.wait_for_certificate.assert_called_once()
        mock_cf.create_s3_distribution.assert_called_once()
        mock_dns.setup_cloudfront_dns.assert_called_once_with(domain=DOMAIN, distribution_domain=DIST_DOMAIN)
        mock_cf.wait_for_distribution.assert_called_once_with(distribution_id=DIST_ID, timeout_minutes=30)

    def test_deploy_full_with_install(self, tmp_path):
        """deploy_full with install=True should call install_dependencies first."""
        patchers = self._patch_all_services(tmp_path)

        with patchers["DeploymentService"] as mock_ds_cls, \
             patchers["AWSCloudFrontService"] as mock_cf_cls, \
             patchers["AWSDomainService"] as mock_dns_cls:

            mock_ds = MagicMock()
            mock_ds_cls.return_value = mock_ds

            mock_cf = MagicMock()
            mock_cf.request_ssl_certificate.return_value = CERT_ARN
            mock_cf.get_acm_validation_records.return_value = [{"name": "_n", "value": "_v"}]
            mock_cf.create_s3_distribution.return_value = {
                "distribution_id": DIST_ID, "distribution_domain": DIST_DOMAIN,
                "status": "InProgress", "arn": "arn:..."
            }
            mock_cf_cls.return_value = mock_cf

            mock_dns = MagicMock()
            mock_dns.add_acm_dns_records.return_value = {"status": "success", "change_id": "C1"}
            mock_dns.setup_cloudfront_dns.return_value = {"status": "success", "hosted_zone_id": "Z1", "change_id": "C2"}
            mock_dns_cls.return_value = mock_dns

            orch = self._make_orchestrator()
            orch.deploy_full(app_dir=tmp_path, bucket_name=BUCKET, domain=DOMAIN, install=True)

        mock_ds.install_dependencies.assert_called_once()

    def test_deploy_full_with_domain_registration(self, tmp_path):
        """deploy_full with contact_info should call register_domain as Step 2."""
        patchers = self._patch_all_services(tmp_path)

        with patchers["DeploymentService"] as mock_ds_cls, \
             patchers["AWSCloudFrontService"] as mock_cf_cls, \
             patchers["AWSDomainService"] as mock_dns_cls:

            mock_ds = MagicMock()
            mock_ds_cls.return_value = mock_ds

            mock_cf = MagicMock()
            mock_cf.request_ssl_certificate.return_value = CERT_ARN
            mock_cf.get_acm_validation_records.return_value = [{"name": "_n", "value": "_v"}]
            mock_cf.create_s3_distribution.return_value = {
                "distribution_id": DIST_ID, "distribution_domain": DIST_DOMAIN,
                "status": "InProgress", "arn": "arn:..."
            }
            mock_cf_cls.return_value = mock_cf

            mock_dns = MagicMock()
            mock_dns.register_domain.return_value = {"operation_id": "op-123", "status": "SUBMITTED"}
            mock_dns.add_acm_dns_records.return_value = {"status": "success", "change_id": "C1"}
            mock_dns.setup_cloudfront_dns.return_value = {"status": "success", "hosted_zone_id": "Z1", "change_id": "C2"}
            mock_dns_cls.return_value = mock_dns

            orch = self._make_orchestrator()
            orch.deploy_full(
                app_dir=tmp_path,
                bucket_name=BUCKET,
                domain=DOMAIN,
                contact_info=CONTACT_INFO,
                duration_years=1,
            )

        mock_dns.register_domain.assert_called_once_with(
            domain=DOMAIN,
            contact_info=CONTACT_INFO,
            duration_years=1,
        )

    def test_deploy_full_raises_orchestrator_error_on_failure(self, tmp_path):
        """deploy_full should wrap any step failure in OrchestratorError."""
        patchers = self._patch_all_services(tmp_path)

        with patchers["DeploymentService"] as mock_ds_cls, \
             patchers["AWSCloudFrontService"] as mock_cf_cls, \
             patchers["AWSDomainService"] as mock_dns_cls:

            mock_ds = MagicMock()
            mock_ds.run_build.side_effect = RuntimeError("Build failed!")
            mock_ds_cls.return_value = mock_ds

            mock_cf_cls.return_value = MagicMock()
            mock_dns_cls.return_value = MagicMock()

            from src.services.deployment_orchestrator import OrchestratorError
            orch = self._make_orchestrator()

            with pytest.raises(OrchestratorError, match="Build failed"):
                orch.deploy_full(app_dir=tmp_path, bucket_name=BUCKET, domain=DOMAIN)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
