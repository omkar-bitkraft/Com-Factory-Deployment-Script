"""
AWS CDN Service
Handles CloudFront distribution creation and configuration for S3-hosted websites.
"""

from typing import Dict, Any, Optional
import time

try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

from src.utils.logger import get_logger
from src.utils.config import get_settings, Settings

logger = get_logger(__name__)


class AWSCDNError(Exception):
    """Base exception for AWS CDN service errors"""
    pass


class AWSCDNService:
    """
    AWS CloudFront Service.
    Handles creation and management of CloudFront distributions.
    """
    
    def __init__(self, config: Optional[Settings] = None):
        """
        Initialize AWS CDN Service.
        
        Args:
            config: Optional Settings object. If None, loads from get_settings()
        """
        if not AWS_AVAILABLE:
            raise ImportError("boto3 is required for AWSCDNService. Install it with: pip install boto3")
        
        self.config = config or get_settings()
        
        # CloudFront client (global)
        self.cloudfront_client = boto3.client(
            'cloudfront',
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key,
            region_name="us-east-1"  # CloudFront api is global (us-east-1)
        )
        
        logger.info("AWSCDNService initialized")

    def create_s3_distribution(self, bucket_name: str, domain_name: str) -> Dict[str, Any]:
        """
        Create a CloudFront distribution for an S3 bucket with a custom domain.
        
        Args:
            bucket_name: Name of the S3 bucket (origin)
            domain_name: Custom domain name (CNAME)
            
        Returns:
            Dictionary with distribution info
        """
        logger.info(f"Creating CloudFront distribution for {bucket_name} ({domain_name})")
        
        # Note: In a production environment, you would also need to:
        # 1. Create/Get an ACM Certificate for the domain (SSL)
        # 2. Configure Origin Access Control (OAC) for S3 security
        # 3. Update S3 Bucket Policy to allow OAC
        
        # For this implementation, we will create a standard distribution pointing to S3 Website Endpoint
        # This allows http-only access initially if no SSL cert is provided, 
        # or we assume the user will attach the cert manually via AWS Console for now 
        # as ACM automation is complex (requires DNS validation).
        
        origin_id = f"S3-{bucket_name}"
        s3_website_endpoint = f"{bucket_name}.s3-website-{self.config.aws_region}.amazonaws.com"
        
        distribution_config = {
            'CallerReference': str(time.time()),
            'Aliases': {
                'Quantity': 1,
                'Items': [domain_name]
            },
            'DefaultRootObject': 'index.html',
            'Origins': {
                'Quantity': 1,
                'Items': [
                    {
                        'Id': origin_id,
                        'DomainName': s3_website_endpoint,
                        'CustomOriginConfig': {
                            'HTTPPort': 80,
                            'HTTPSPort': 443,
                            'OriginProtocolPolicy': 'http-only',
                            'OriginSslProtocols': {
                                'Quantity': 3,
                                'Items': ['TLSv1', 'TLSv1.1', 'TLSv1.2'] 
                            }
                        }
                    }
                ]
            },
            'DefaultCacheBehavior': {
                'TargetOriginId': origin_id,
                'ForwardedValues': {
                    'QueryString': False,
                    'Cookies': {'Forward': 'none'}
                },
                'TrustedSigners': {'Enabled': False, 'Quantity': 0},
                'ViewerProtocolPolicy': 'allow-all',  # Change to 'redirect-to-https' if SSL is set up
                'MinTTL': 0
            },
            'CacheBehaviors': {'Quantity': 0},
            'CustomErrorResponses': {'Quantity': 0},
            'Comment': f'Created by AWSCDNService for {domain_name}',
            'Enabled': True
        }
        
        try:
            response = self.cloudfront_client.create_distribution(
                DistributionConfig=distribution_config
            )
            
            dist = response['Distribution']
            dist_id = dist['Id']
            dist_domain = dist['DomainName']
            
            logger.info(f"✅ CloudFront Distribution created: {dist_id}")
            logger.info(f"Domain Name: {dist_domain}")
            logger.warning("⚠️ Note: It may take 15-20 minutes for the distribution to be fully deployed.")
            logger.warning("⚠️ Action Required: Ensure you have an SSL certificate in US-EAST-1 if later enforcing HTTPS.")
            
            return {
                "distribution_id": dist_id,
                "distribution_domain": dist_domain,
                "status": dist['Status'],
                "arn": dist['ARN']
            }
            
        except ClientError as e:
            logger.error(f"Failed to create CloudFront distribution: {str(e)}")
            raise AWSCDNError(f"CloudFront creation failed: {str(e)}")
