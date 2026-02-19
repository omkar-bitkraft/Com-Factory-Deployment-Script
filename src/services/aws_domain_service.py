"""
AWS Domain Service
Standalone service for AWS Route53 domain registration and DNS configuration.
Provides seamless integration between domain purchase and S3 website deployment.
"""

import time
from typing import Dict, Any, List, Optional, TypedDict
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

class ContactDetail(TypedDict):
    """AWS-compatible contact detail structure"""
    FirstName: str
    LastName: str
    ContactType: str  # PERSON, COMPANY, ASSOCIATION, etc.
    OrganizationName: Optional[str]
    AddressLine1: str
    AddressLine2: Optional[str]
    City: str
    State: str
    CountryCode: str  # ISO 3166-1 alpha-2
    ZipCode: str
    PhoneNumber: str  # Format: +CC.NNNNNNNNNN
    Email: str
    ExtraParams: Optional[List[Dict[str, str]]]

class AWSContactInfo(TypedDict):
    """Complete contact information for domain registration"""
    AdminContact: ContactDetail
    RegistrantContact: ContactDetail
    TechContact: ContactDetail
    Privacy: bool
    AutoRenew: bool

from src.utils.logger import get_logger
from src.utils.config import get_settings, Settings

logger = get_logger(__name__)


class AWSDomainError(Exception):
    """Base exception for AWS domain service errors"""
    pass


class AWSDomainService:
    """
    Standalone AWS Domain Service.
    Handles Route53 domain registration and DNS setup.
    """
    
    def __init__(self, region: str = "us-east-1", config: Optional[Settings] = None):
        """
        Initialize AWS Domain Service.
        
        Args:
            region: AWS region (domain registration is global but endpoint is us-east-1)
            config: Optional Settings object. If None, loads from get_settings()
        """
        if not AWS_AVAILABLE:
            raise ImportError("boto3 is required for AWSDomainService. Install it with: pip install boto3")
        
        self.config = config or get_settings()
        self.region = region
        
        # Domain registration client (must be us-east-1)
        self.domains_client = boto3.client(
            'route53domains',
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key,
            region_name="us-east-1"
        )
        
        # DNS management client
        self.route53_client = boto3.client(
            'route53',
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key,
            region_name=self.region
        )
        
        logger.info(f"AWSDomainService initialized (Region: {self.region})")

    def check_availability(self, domain: str) -> Dict[str, Any]:
        """
        Check if a domain is available for purchase.
        
        Returns:
            Dictionary with availability info
        """
        logger.info(f"Checking AWS domain availability: {domain}")
        try:
            response = self.domains_client.check_domain_availability(
                DomainName=domain
            )
            availability = response.get('Availability')
            is_available = availability == 'AVAILABLE'
            
            logger.info(f"Domain {domain} status: {availability}")
            
            return {
                "domain": domain,
                "available": is_available,
                "status": availability,
                "provider": "AWS-Route53"
            }
        except ClientError as e:
            logger.error(f"AWS API error: {str(e)}")
            raise AWSDomainError(f"Failed to check availability: {str(e)}")

    def get_suggestions(self, domain: str) -> List[str]:
        """Get domain suggestions"""
        logger.info(f"Getting AWS domain suggestions for: {domain}")
        try:
            response = self.domains_client.get_domain_suggestions(
                DomainName=domain,
                OnlyAvailable=True,
                SuggestionCount=10
            )
            suggestions = [s.get('DomainName') for s in response.get('SuggestionsList', [])]
            return suggestions
        except ClientError as e:
            logger.error(f"AWS API error: {str(e)}")
            return []

    def register_domain(self, domain: str, contact_info: AWSContactInfo, duration: int = 1) -> Dict[str, Any]:
        """
        Register a new domain.
        
        Args:
            domain: Domain name
            contact_info: AWS-formatted contact info (see AWSContactInfo TypedDict)
            duration: Registration period in years
        """
        logger.info(f"Registering domain on AWS: {domain} for {duration} year(s)")
        
        # AWS requires specific keys for contact info: AdminContact, RegistrantContact, TechContact
        # This implementation expects contact_info to already be in the correct AWS format or 
        # a simplified format that we map here.
        
        try:
            response = self.domains_client.register_domain(
                DomainName=domain,
                DurationInYears=duration,
                AdminContact=contact_info.get('AdminContact', contact_info),
                RegistrantContact=contact_info.get('RegistrantContact', contact_info),
                TechContact=contact_info.get('TechContact', contact_info),
                PrivacyProtectAdminContact=contact_info.get('Privacy', True),
                PrivacyProtectRegistrantContact=contact_info.get('Privacy', True),
                PrivacyProtectTechContact=contact_info.get('Privacy', True),
                AutoRenew=contact_info.get('AutoRenew', True)
            )
            
            operation_id = response.get('OperationId')
            logger.info(f"✅ Registration request submitted. Operation ID: {operation_id}")
            
            return {
                "domain": domain,
                "status": "pending",
                "operation_id": operation_id,
                "message": "Domain registration request submitted successfully."
            }
        except ClientError as e:
            logger.error(f"AWS Registration error: {str(e)}")
            raise AWSDomainError(f"Registration failed: {str(e)}")
