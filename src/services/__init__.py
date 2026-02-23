"""
Business logic and service layer
"""

from src.services.deployment_service import DeploymentService, DeploymentError, BuildError
from src.services.domain_service import DomainService, DomainServiceError
from src.services.aws_domain_service import AWSDomainService, AWSDomainError
from src.services.aws_cdn_service import (
    AWSCloudFrontService,
    AWSCloudFrontError,
    # Backwards-compatible aliases
    AWSCDNService,
    AWSCDNError,
)
from src.services.deployment_orchestrator import DeploymentOrchestrator, OrchestratorError

__all__ = [
    # Deployment
    "DeploymentService",
    "DeploymentError",
    "BuildError",
    # Domain providers (GoDaddy / DNSimple)
    "DomainService",
    "DomainServiceError",
    # AWS Domain (Route53)
    "AWSDomainService",
    "AWSDomainError",
    # AWS CloudFront + ACM
    "AWSCloudFrontService",
    "AWSCloudFrontError",
    # Backwards-compatible aliases
    "AWSCDNService",
    "AWSCDNError",
    # Pipeline orchestrator
    "DeploymentOrchestrator",
    "OrchestratorError",
]
