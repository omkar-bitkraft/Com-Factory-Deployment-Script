"""
DNSimple Domain API Client
Handles all interactions with DNSimple API
"""

import requests
from typing import Dict, Any, List, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from src.api.base_provider import BaseDomainProvider
from src.utils.config import get_settings, Settings
from src.utils.logger import get_logger
from src.utils.validators import validate_domain
from src.api.exceptions import (
    APIError as DomainAPIError,  # Reuse existing exceptions
    AuthenticationError,
    DomainNotAvailableError,
    DomainNotFoundError,
    RateLimitError,
    InvalidDomainError,
    ValidationError as APIValidationError,
    NetworkError,
    ServerError
)

logger = get_logger(__name__)


class DNSimpleClient(BaseDomainProvider):
    """
    DNSimple API client for domain operations.
    
    Documentation: https://developer.dnsimple.com/v2/
    """
    
    def __init__(self, config: Optional[Settings] = None):
        """
        Initialize DNSimple client.
        
        Args:
            config: Optional Settings instance. Uses default config if None.
        """
        self.config = config or get_settings()
        
        # DNSimple configuration
        self.api_token = self.config.dnsimple_api_token
        self.account_id = self.config.dnsimple_account_id
        self.sandbox = self.config.dnsimple_sandbox
        
        # Set base URL based on environment
        if self.sandbox:
            self.base_url = "https://api.sandbox.dnsimple.com"
        else:
            self.base_url = "https://api.dnsimple.com"
        
        # Setup headers
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logger.info(f"DNSimple client initialized - Environment: {'SANDBOX' if self.sandbox else 'PRODUCTION'}")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Account ID: {self.account_id}")
    
    def get_environment(self) -> str:
        """Get current environment"""
        return "SANDBOX" if self.sandbox else "PRODUCTION"
    
    def is_production(self) -> bool:
        """Check if in production"""
        return not self.sandbox
    
    def get_provider_name(self) -> str:
        """Get provider name"""
        return "DNSimple"
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to DNSimple API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON body
            
        Returns:
            Response data
            
        Raises:
            Various API exceptions
        """
        url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"{method} {url}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=30
            )
            
            # Handle response codes
            if response.status_code in [200, 201, 204]:
                if response.content:
                    return response.json()
                return {}
            
            # Error handling
            error_data = response.json() if response.content else {}
            error_message = error_data.get("message", response.text)
            
            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid DNSimple API token",
                    status_code=401,
                    response_data=error_data
                )
            
            elif response.status_code == 404:
                raise DomainNotFoundError(
                    error_message,
                    status_code=404,
                    response_data=error_data
                )
            
            elif response.status_code == 429:
                raise RateLimitError(
                    "DNSimple API rate limit exceeded",
                    status_code=429,
                    response_data=error_data
                )
            
            elif response.status_code >= 500:
                raise ServerError(
                    f"DNSimple server error: {error_message}",
                    status_code=response.status_code,
                    response_data=error_data
                )
            
            else:
                raise DomainAPIError(
                    f"DNSimple API error: {error_message}",
                    status_code=response.status_code,
                    response_data=error_data
                )
        
        except requests.exceptions.Timeout:
            raise NetworkError("Request timed out after 30 seconds")
        
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError, RateLimitError)),
        reraise=True
    )
    def get_domain_prices(self, domain: str) -> Dict[str, Any]:
        """
        Get domain prices.
        
        Args:
            domain: Domain name
            
        Returns:
            Price data
        """
        endpoint = f"/v2/{self.account_id}/registrar/domains/{domain}/prices"
        response = self._make_request("GET", endpoint)
        return response.get("data", {})

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError, RateLimitError)),
        reraise=True
    )
    def check_availability(self, domain: str) -> Dict[str, Any]:
        """
        Check domain availability.
        
        Args:
            domain: Domain name
            
        Returns:
            {
                "available": bool,
                "domain": str,
                "price": float,
                "currency": str,
                "period": int
            }
        """
        domain = validate_domain(domain)
        logger.info(f"Checking availability: {domain}")
        
        endpoint = f"/v2/{self.account_id}/registrar/domains/{domain}/check"
        response = self._make_request("GET", endpoint)
        
        # DNSimple response format
        data = response.get("data", {})
        available = data.get("available", False)
        expiresAt = data.get("expires_at", None)
        
        # Get pricing if available
        price = 0.0
        if available:
            try:
                prices = self.get_domain_prices(domain)
                price = float(prices.get("registration_price", 0.0))
            except Exception as e:
                logger.warning(f"Failed to fetch prices for {domain}: {str(e)}")
        
        # Check for premium price in the check response (older API behavior, but good fallback)
        elif "premium_price" in data:
            price = float(data["premium_price"])
        
        result = {
            "available": available,
            "domain": domain,
            "price": price,
            "currency": "USD",  # DNSimple uses USD
            "expiresAt": expiresAt,
            "definitive": True
        }
        
        logger.info(f"Domain {domain} - Available: {available} - Price: ${price}")
        return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def suggest_domains(self, query: str, limit: int = 10) -> List[str]:
        """
        Get domain suggestions.
        
        Note: DNSimple doesn't have a suggestions API, so we'll generate
        common variations of the query.
        
        Args:
            query: Search query
            limit: Max suggestions
            
        Returns:
            List of suggested domains
        """
        # logger.info(f"Generating suggestions for: {query}")
        
        # # Create common variations
        # base = query.lower().replace(" ", "")
        # tlds = [".com", ".net", ".io", ".app", ".dev", ".co"]
        # prefixes = ["", "get", "my", "the"]
        # suffixes = ["", "app", "hq", "io", "online"]
        
        # suggestions = []
        
        # # Generate combinations
        # for tld in tlds:
        #     suggestions.append(f"{base}{tld}")
            
        #     for prefix in prefixes:
        #         if prefix:
        #             suggestions.append(f"{prefix}{base}{tld}")
            
        #     for suffix in suffixes:
        #         if suffix:
        #             suggestions.append(f"{base}{suffix}{tld}")
        
        # # Return unique suggestions up to limit
        # unique_suggestions = list(dict.fromkeys(suggestions))
        # return unique_suggestions[:limit]
        logger.info(f"DNSimple does not support domain suggestions via API")
        raise NotImplementedError("DNSimple does not support domain suggestions via API")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError, RateLimitError)),
        reraise=True
    )
    def create_contact(self, contact_info: Dict[str, Any]) -> int:
        """
        Create a contact in DNSimple.
        
        Args:
            contact_info: Contact details (matches DomainService format)
            
        Returns:
            Contact ID
        """
        logger.info("Creating new contact in DNSimple")
        
        try:
            # Map to DNSimple keys
            # Handle both nested addressMailing and top-level keys, and GoDaddy vs DNSimple naming conventions
            address = contact_info.get("addressMailing", {})
            
            payload = {
                "first_name": contact_info.get("nameFirst", contact_info.get("first_name")),
                "last_name": contact_info.get("nameLast", contact_info.get("last_name")),
                "email": contact_info.get("email"),
                "phone": contact_info.get("phone"),
                "address1": address.get("address1", contact_info.get("address1")),
                "city": address.get("city", contact_info.get("city")),
                "state_province": address.get("state", contact_info.get("state_province", contact_info.get("state"))),
                "postal_code": address.get("postalCode", contact_info.get("postal_code", contact_info.get("postalCode"))),
                "country": address.get("country", contact_info.get("country"))
            }
            
            logger.info(f"DNSimple Contact Payload: {payload}")

            # Check for organization (optional)
            if "organization" in contact_info:
                payload["organization_name"] = contact_info["organization"]
            
            endpoint = f"/v2/{self.account_id}/contacts"
            response = self._make_request("POST", endpoint, json_data=payload)
            
            contact_id = response.get("data", {}).get("id")
            logger.info(f"Created contact with ID: {contact_id}")
            return contact_id
        except Exception as e:
            logger.error(f"Failed to create contact: {str(e)}")
            raise APIValidationError("Failed to create contact in DNSimple. Please ensure all required fields are provided and valid.")
        
    def get_contact(self) -> Dict[str, Any]:
        """
        Get contact details.
        """ 
        try:
            logger.info("Fetching contact details from DNSimple")
            endpoint = f"/v2/{self.account_id}/contacts"
            contact_info = self._make_request("GET", endpoint)
            return contact_info.get("data", {})
        except Exception as e:
            logger.error(f"Failed to fetch contact details: {str(e)}")
            raise APIValidationError("Failed to fetch contact details from DNSimple: "+ str(e))

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def purchase_domain(
        self,
        domain: str,
        contact_info: Dict[str, Any],
        period: int = 1,
        privacy: bool = False,
        auto_renew: bool = False
    ) -> Dict[str, Any]:
        """
        Purchase domain from DNSimple.
        
        Args:
            domain: Domain to purchase
            contact_info: Registrant contact info
            period: Registration period in years
            privacy: Enable WHOIS privacy
            auto_renew: Enable auto-renewal
            
        Returns:
            Purchase result
        """
        domain = validate_domain(domain)
        
        if self.is_production():
            logger.warning("⚠️  REAL PURCHASE IN PRODUCTION ENVIRONMENT!")
        
        logger.info(f"Purchasing process for domain: {domain}")
        
        # Get or create registrant
        registrant_id = contact_info.get("registrant_id") if contact_info else None
        
        if not registrant_id:
            try:
                registrant_id = self.config.dnsimple_registrant_id
                if not registrant_id:
                    # Attempt to create contact from provided info
                    registrant_id = self.create_contact(contact_info)
                logger.info(f"Using registrant ID: {registrant_id} for domain purchase")
            except Exception as e:
                logger.error(f"Failed to create contact: {str(e)}")
                raise APIValidationError("DNSimple requires a valid 'registrant_id' or complete contact info")

        # DNSimple registration payload
        payload: Dict[str, Any] = {
            "registrant_id": int(registrant_id),
            "auto_renew": auto_renew,
            "whois_privacy": privacy
        }
        
        # Add premium price if provided (required for premium domains)
        if contact_info and "premium_price" in contact_info:
            payload["premium_price"] = str(contact_info["premium_price"])
        
        endpoint = f"/v2/{self.account_id}/registrar/domains/{domain}/registrations"
        response = self._make_request("POST", endpoint, json_data=payload)
        
        # Parse response
        data = response.get("data", {})
        
        result = {
            "orderId": data.get("id"),
            "domain": data.get("domain_name", domain),  # API returns domain_id usually, but let's check schema
            "status": data.get("state"),
            "period": data.get("period", period)  # Use actual period from response or requested as fallback
        }
        
        logger.info(f"✅ Domain {domain} purchased successfully!")
        return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def get_domains(self) -> List[Dict[str, Any]]:
        """
        Get list of owned domains.
        Handles pagination to fetch all domains.
        
        Returns:
            List of domain dictionaries
        """
        logger.info("Fetching owned domains from DNSimple")
        
        all_domains = []
        page = 1
        per_page = 100  # Maximize page size
        
        while True:
            endpoint = f"/v2/{self.account_id}/domains"
            params = {"page": page, "per_page": per_page}
            
            response = self._make_request("GET", endpoint, params=params)
            print("Response List........", response)
            
            data = response.get("data", [])
            pagination = response.get("pagination", {})
            
            if not data:
                break
                
            all_domains.extend(data)
            
            # Check if we need to fetch more
            current_page = pagination.get("current_page", page)
            total_pages = pagination.get("total_pages", 1)
            
            if current_page >= total_pages:
                break
                
            page += 1
        
        # Format response to match expected structure
        formatted_domains = []
        for domain_data in all_domains:
            formatted_domains.append({
                "domain": domain_data.get("name"),
                "status": domain_data.get("state"),
                "createdAt": domain_data.get("created_at"),
                "expires": domain_data.get("expires_at"),
                "renewAuto": domain_data.get("auto_renew", False)
            })
        
        logger.info(f"Found {len(formatted_domains)} domains in DNSimple account")
        return formatted_domains
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def get_domain_details(self, domain: str) -> Dict[str, Any]:
        """
        Get domain details.
        
        Args:
            domain: Domain name
            
        Returns:
            Domain details
        """
        logger.info(f"Getting details for: {domain}")
        
        endpoint = f"/v2/{self.account_id}/domains/{domain}"
        response = self._make_request("GET", endpoint)
        
        data = response.get("data", {})
        
        # Format response
        details = {
            "domain": data.get("name"),
            "domainId": data.get("id"),
            "status": data.get("state"),
            "createdAt": data.get("created_at"),
            "expires": data.get("expires_at"),
            "renewAuto": data.get("auto_renew", False),
            "privacy": data.get("private_whois", False)
        }
        
        return details
    
    def validate_purchase(
        self,
        domain: str,
        contact_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate domain purchase.
        
        Note: DNSimple doesn't have a separate validation endpoint,
        so we just check availability.
        
        Args:
            domain: Domain to validate
            contact_info: Contact info
            
        Returns:
            Validation result
        """
        logger.info(f"Validating purchase for: {domain}")
        
        availability = self.check_availability(domain)
        
        if not availability.get("available"):
            raise DomainNotAvailableError(f"Domain {domain} is not available")
        
        return {"valid": True, "domain": domain}
