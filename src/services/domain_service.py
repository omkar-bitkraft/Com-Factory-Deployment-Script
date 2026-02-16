"""
Domain Service
High-level business logic for domain operations
Orchestrates GoDaddy API client for common domain workflows
"""

from typing import Dict, Any, List, Optional

from src.api import BaseDomainProvider, get_domain_provider
from src.api.exceptions import (
    DomainNotAvailableError,
    InvalidDomainError,
    InsufficientFundsError
)
from src.utils.logger import get_logger
from src.utils.validators import validate_domain, validate_email, ValidationError

logger = get_logger(__name__)


class DomainServiceError(Exception):
    """Base exception for domain service errors"""
    pass


class DomainService:
    """
    High-level domain operations service.
    Provides user-friendly interface for domain management.
    Supports multiple domain providers (GoDaddy, DNSimple, etc.)
    """
    
    def __init__(self, provider: Optional[BaseDomainProvider] = None, provider_name: Optional[str] = None):
        """
        Initialize domain service.
        
        Args:
            provider: Optional provider instance. If None, creates from config.
            provider_name: Optional provider name ("GODADDY" or "DNSIMPLE").
                          If None, reads from config.
                          
        Example:
            # Use configured provider
            service = DomainService()
            
            # Use specific provider
            service = DomainService(provider_name="DNSIMPLE")
            
            # Use custom provider instance
            custom_provider = DNSimpleClient()
            service = DomainService(provider=custom_provider)
        """
        if provider:
            self.client = provider
        else:
            self.client = get_domain_provider(provider_name)
        
        logger.info(f"Domain service initialized")
        logger.info(f"Provider: {self.client.get_provider_name()}")
        logger.info(f"Environment: {self.client.get_environment()}")
    
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """
        Search for domain availability with validation and formatting.
        
        Args:
            domain: Domain name to search
            
        Returns:
            Dictionary with availability info and formatted data
            
        Raises:
            DomainServiceError: If search fails
        """
        try:
            # Validate domain format
            domain = validate_domain(domain)
            logger.info(f"Searching domain: {domain}")
            
            # Check availability
            result = self.client.check_availability(domain)
            
            # Format response
            formatted_result = {
                "domain": domain,
                "available": result.get("available", False),
                "definitive": result.get("definitive", False),
                "price": result.get("price", 0),
                "currency": result.get("currency", "USD"),
                "period": result.get("period", None),
                "expires_at": result.get("expiresAt", None),
                "raw_response": result
            }
            # Log result
            if formatted_result["available"]:
                logger.info(f"✅ {domain} is AVAILABLE - ${formatted_result['price']:.2f} {formatted_result['currency']}")
            else:
                logger.info(f"❌ {domain} is NOT available")
            
            return formatted_result
            
        except ValidationError as e:
            logger.error(f"Invalid domain: {str(e)}")
            raise DomainServiceError(f"Invalid domain format: {str(e)}") from e
        
        except Exception as e:
            logger.error(f"API error searching domain: {str(e)}")
            raise DomainServiceError(f"Domain search failed: {str(e)}") from e
    
    def search_multiple_domains(self, domains: List[str]) -> List[Dict[str, Any]]:
        """
        Search multiple domains for availability.
        
        Args:
            domains: List of domain names
            
        Returns:
            List of availability results
        """
        results = []
        
        for domain in domains:
            try:
                result = self.search_domain(domain)
                results.append(result)
            except DomainServiceError as e:
                logger.warning(f"Skipping {domain}: {str(e)}")
                results.append({
                    "domain": domain,
                    "available": False,
                    "error": str(e)
                })
        return results
    
    def get_suggestions(
        self,
        query: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get domain name suggestions based on keywords.
        
        Args:
            query: Search query
            limit: Maximum suggestions
            
        Returns:
            List of suggested domain names
        """
        logger.info(f"Getting suggestions for '{query}' (limit: {limit})")
        
        try:
            suggestions = self.client.suggest_domains(query, limit=limit)
            logger.info(f"Found {len(suggestions)} suggestions")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {str(e)}")
            raise DomainServiceError(f"{str(e)}") from e
    
    def purchase_domain_workflow(
        self,
        domain: str,
        contact_info: Dict[str, Any],
        period: int = 1,
        privacy: bool = False,
        auto_renew: bool = False,
        validate_first: bool = True,
        confirm_purchase: bool = True
    ) -> Dict[str, Any]:
        """
        Complete domain purchase workflow with validation and confirmation.
        
        Args:
            domain: Domain to purchase
            contact_info: Contact information dictionary
            period: Registration period in years
            privacy: Enable domain privacy
            validate_first: Validate purchase before executing
            confirm_purchase: Require user confirmation
            
        Returns:
            Purchase result dictionary
            
        Raises:
            DomainServiceError: If purchase fails
        """
        logger.info(f"Starting purchase workflow for: {domain}")
        
        try:
            # Step 1: Validate domain format
            domain = validate_domain(domain)
            
            # Step 2: Check availability
            logger.info("Step 1: Checking domain availability...")
            availability = self.client.check_availability(domain)
            
            if not availability.get("available"):
                raise DomainServiceError(f"Domain {domain} is not available for purchase")
            
            # Log availability
            price = availability.get("price", 0)
            logger.info(f"✅ Domain {domain} is available - ${price:.2f} {availability.get('currency', 'USD')} for {period} year(s)")
            
            # Step 3: Validate contact info
            logger.info("Skipping.... Step 2: Validating contact information...")
            # self._validate_contact_info(contact_info)
    
            # Step 4: Confirm with user
            if confirm_purchase:
                if self.client.is_production():
                    logger.warning("⚠️  WARNING: PRODUCTION ENVIRONMENT - REAL PURCHASE!")
                    logger.warning(f"Domain: {domain} | Amount: ${price:.2f}")
                    response = input("\nProceed with REAL purchase? (yes/no): ")
                else:
                    logger.info(f"OTE Test Purchase: {domain} - ${price:.2f}")
                    response = input("\nProceed with test purchase? (yes/no): ")
                
                if response.lower() not in ["yes", "y"]:
                    logger.info("Purchase cancelled by user")
                    return {"status": "cancelled", "domain": domain}
            
            # Step 6: Purchase domain
            logger.info("Step 4: Purchasing domain...")
            result = self.client.purchase_domain(
                domain=domain,
                contact_info=contact_info,
                period=period,
                privacy=privacy,
                auto_renew=auto_renew
            )
            
            logger.info(f"✅ Domain Purchased Successfully! - {domain}")
            logger.info(f"Order ID: {result.get('orderId', 'N/A')}")
            
            return result
            
        except DomainNotAvailableError:
            raise DomainServiceError(f"Domain {domain} is not available")
        
        except InsufficientFundsError:
            raise DomainServiceError("Insufficient funds in GoDaddy account")
        
        except Exception as e:
            logger.error(f"Purchase failed: {str(e)}")
            raise DomainServiceError(f"Purchase failed: {str(e)}") from e
    
    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """
        Get list of domains owned by the account.
        
        Returns:
            List of domain dictionaries
        """
        logger.info("Fetching owned domains")
        
        try:
            domains = self.client.get_domains()
            logger.info(f"Found {len(domains)} owned domains")
            
            return domains
            
        except DomainServiceError as e:
            logger.error(f"Error fetching domains: {str(e)}")
            raise DomainServiceError(f"Failed to fetch domains: {str(e)}") from e
    
    def get_domain_info(
        self,
        domain: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Domain details dictionary
        """
        logger.info(f"Getting details for: {domain}")
        
        try:
            details = self.client.get_domain_details(domain)
            logger.info(f"Retrieved details for {domain}")
            
            return details
            
        except DomainServiceError as e:
            logger.error(f"Error getting domain details: {str(e)}")
            raise DomainServiceError(f"Failed to get domain details: {str(e)}") from e
    
    def _validate_contact_info(self, contact: Dict[str, Any]):
        """
        Validate contact information.
        
        Args:
            contact: Contact information dictionary
            
        Raises:
            DomainServiceError: If validation fails
        """
        required_fields = [
            "nameFirst", "nameLast", "email", "phone", "addressMailing"
        ]
        
        for field in required_fields:
            if field not in contact:
                raise DomainServiceError(f"Missing required field: {field}")
        
        # Validate email
        try:
            validate_email(contact["email"])
        except ValidationError as e:
            raise DomainServiceError(f"Invalid email: {str(e)}") from e
        
        # Validate address
        address = contact.get("addressMailing", {})
        required_address_fields = ["address1", "city", "state", "postalCode", "country"]
        
        for field in required_address_fields:
            if field not in address:
                raise DomainServiceError(f"Missing address field: {field}")
