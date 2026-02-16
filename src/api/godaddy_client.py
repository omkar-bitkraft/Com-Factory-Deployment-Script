"""
GoDaddy Domain API Client
Handles all interactions with GoDaddy Domain API
"""

import time
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
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
    APIError,
    AuthenticationError,
    DomainNotAvailableError,
    DomainNotFoundError,
    InsufficientFundsError,
    RateLimitError,
    InvalidDomainError,
    NetworkError,
    ValidationError,
    ServerError
)


logger = get_logger(__name__)


class GoDaddyClient(BaseDomainProvider):
    """
    GoDaddy API Client for domain operations.
    Supports both OTE (test) and Production environments.
    """
    
    def __init__(self, config=None):
        """
        Initialize GoDaddy API client.
        
        Args:
            config: Optional Settings object. If None, loads from get_settings()
        """
        self.config = config or get_settings()
        self.base_url = self.config.godaddy_base_url
        self.headers = {
            **self.config.godaddy_auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logger.info(f"GoDaddy Client initialized - Environment: {self.config.godaddy_env}")
        logger.info(f"Base URL: {self.base_url}")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to GoDaddy API with error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/v1/domains/available')
            params: Query parameters
            json_data: JSON body for POST/PUT requests
            
        Returns:
            Response data as dictionary
            
        Raises:
            Various GoDaddyAPIError subclasses based on error type
        """
        url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"{method} {url}")
        if params:
            logger.debug(f"Params: {params}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=30
            )
            
            # Handle different HTTP status codes
            if response.status_code == 200:
                # Success
                return response.json() if response.content else {}
            
            elif response.status_code == 201:
                # Created
                return response.json() if response.content else {}
            
            elif response.status_code == 204:
                # No content (success)
                return {}
            
            elif response.status_code == 400:
                # Bad request / validation error
                error_data = self._parse_error_response(response)
                raise ValidationError(
                    error_data.get("message", "Bad request"),
                    status_code=400,
                    response_data=error_data
                )
            
            elif response.status_code == 401:
                # Unauthorized
                raise AuthenticationError(
                    "Authentication failed. Check your GoDaddy API key and secret.",
                    status_code=401
                )
            
            elif response.status_code == 403:
                # Forbidden
                error_data = self._parse_error_response(response)
                raise AuthenticationError(
                    error_data.get("message", "Access forbidden"),
                    status_code=403,
                    response_data=error_data
                )
            
            elif response.status_code == 404:
                # Not found
                error_data = self._parse_error_response(response)
                raise DomainNotFoundError(
                    error_data.get("message", "Resource not found"),
                    status_code=404,
                    response_data=error_data
                )
            
            elif response.status_code == 422:
                # Domain not available
                error_data = self._parse_error_response(response)
                raise DomainNotAvailableError(
                    error_data.get("message", "Domain not available"),
                    status_code=422,
                    response_data=error_data
                )
            
            elif response.status_code == 429:
                # Rate limit exceeded
                raise RateLimitError(
                    "API rate limit exceeded. Please wait before retrying.",
                    status_code=429
                )
            
            elif response.status_code == 402:
                # Payment required / insufficient funds
                error_data = self._parse_error_response(response)
                raise InsufficientFundsError(
                    error_data.get("message", "Insufficient funds"),
                    status_code=402,
                    response_data=error_data
                )
            
            elif 500 <= response.status_code < 600:
                # Server error
                error_data = self._parse_error_response(response)
                raise ServerError(
                    f"GoDaddy server error: {error_data.get('message', 'Internal server error')}",
                    status_code=response.status_code,
                    response_data=error_data
                )
            
            else:
                # Unknown error
                error_data = self._parse_error_response(response)
                raise APIError(
                    f"Unexpected error: {error_data.get('message', 'Unknown error')}",
                    status_code=response.status_code,
                    response_data=error_data
                )
        
        except requests.exceptions.Timeout:
            raise NetworkError("Request timed out after 30 seconds")
        
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {str(e)}")
        
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Network error: {str(e)}")
    
    def _parse_error_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Parse error response from GoDaddy API.
        
        Args:
            response: Response object
            
        Returns:
            Error data dictionary
        """
        try:
            error_data = response.json()
            return error_data
        except Exception:
            return {
                "message": response.text or "Unknown error",
                "code": response.status_code
            }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError, RateLimitError)),
        reraise=True
    )
    def check_availability(self, domain: str) -> Dict[str, Any]:
        """
        Check if a domain is available for purchase.
        
        Args:
            domain: Domain name to check (e.g., 'example.com')
            
        Returns:
            Dictionary with availability information:
            {
                "available": bool,
                "domain": str,
                "definitive": bool,
                "price": int (in micros),
                "currency": str,
                "period": int (years)
            }
            
        Raises:
            InvalidDomainError: If domain format is invalid
            GoDaddyAPIError: For API errors
        """
        # Validate domain format
        try:
            domain = validate_domain(domain)
        except Exception as e:
            raise InvalidDomainError(f"Invalid domain format: {str(e)}")
        
        logger.info(f"Checking availability for: {domain}")
        
        endpoint = f"/v1/domains/available"
        params = {"domain": domain}
        
        response = self._make_request("GET", endpoint, params=params)
        
        logger.info(f"Domain {domain} - Available: {response.get('available', False)}")
        
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def suggest_domains(self, query: str, limit: int = 10) -> List[str]:
        """
        Get domain suggestions based on a query.
        
        Args:
            query: Search query (e.g., 'coffee shop')
            limit: Maximum number of suggestions (default 10)
            
        Returns:
            List of suggested domain names
        """
        logger.info(f"Getting domain suggestions for: {query}")
        
        endpoint = f"/v1/domains/suggest"
        params = {
            "query": query,
            "limit": limit
        }
        
        response = self._make_request("GET", endpoint, params=params)
        
        # Response is a list of domain objects
        suggestions = [item.get("domain") for item in response if item.get("domain")]
        
        logger.info(f"Found {len(suggestions)} suggestions")
        
        return suggestions
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def get_domain_schema(self, tld: str) -> Dict[str, Any]:
        """
        Get the schema for domain purchase (required contact information).
        
        Args:
            tld: Top-level domain (e.g., 'com', 'net', 'org')
            
        Returns:
            Schema dictionary with required fields
        """
        logger.info(f"Getting domain schema for TLD: {tld}")
        
        endpoint = f"/v1/domains/purchase/schema/{tld}"
        
        response = self._make_request("GET", endpoint)
        
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def validate_purchase(self, domain: str, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a domain purchase request without actually purchasing.
        
        Args:
            domain: Domain to validate
            contact_info: Contact information dictionary
            
        Returns:
            Validation result
        """
        logger.info(f"Validating purchase for: {domain}")
        
        endpoint = f"/v1/domains/purchase/validate"
        
        purchase_data = {
            "domain": domain,
            "consent": {
                "agreementKeys": ["DNRA"],
                "agreedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "agreedBy": contact_info.get("email", "")
            },
            "contactAdmin": contact_info,
            "contactBilling": contact_info,
            "contactRegistrant": contact_info,
            "contactTech": contact_info
        }
        
        response = self._make_request("POST", endpoint, json_data=purchase_data)
        
        return response
    
    @retry(
        stop=stop_after_attempt(2),  # Only retry once for purchases
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
        Purchase a domain.
        
        Args:
            domain: Domain to purchase
            contact_info: Contact information dictionary with fields:
                - nameFirst, nameLast
                - email, phone
                - addressMailing (address1, city, state, postalCode, country)
            period: Registration period in years (default 1)
            privacy: Enable domain privacy (default False)
            auto_renew: Enable auto-renewal (default False)
            
        Returns:
            Purchase confirmation data
            
        Raises:
            InsufficientFundsError: If account lacks funds
            DomainNotAvailableError: If domain is not available
        """
        logger.info(f"Attempting to purchase domain: {domain}")
        logger.warning("⚠️  REAL PURCHASE ATTEMPT - Ensure you're in OTE environment for testing!")
        
        endpoint = f"/v1/domains/purchase"
        
        purchase_data = {
            "domain": domain,
            "period": period,
            "privacy": privacy,
            "renewAuto": auto_renew,
            "consent": {
                "agreementKeys": ["DNRA"],
                "agreedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "agreedBy": contact_info.get("email", "")
            },
            "contactAdmin": contact_info,
            "contactBilling": contact_info,
            "contactRegistrant": contact_info,
            "contactTech": contact_info
        }
        
        response = self._make_request("POST", endpoint, json_data=purchase_data)
        
        logger.info(f"✅ Domain {domain} purchased successfully!")
        
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def get_domains(self) -> List[Dict[str, Any]]:
        """
        Get list of domains owned by the account.
        
        Returns:
            List of domain objects
        """
        logger.info("Fetching owned domains")
        
        endpoint = "/v1/domains"
        
        response = self._make_request("GET", endpoint)
        
        # Response is a list of domain objects
        if isinstance(response, list):
            logger.info(f"Found {len(response)} domains in account")
            return response
        
        return []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((NetworkError, ServerError)),
        reraise=True
    )
    def get_domain_details(self, domain: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Domain details dictionary
        """
        logger.info(f"Getting details for domain: {domain}")
        
        endpoint = f"/v1/domains/{domain}"
        
        response = self._make_request("GET", endpoint)
        
        return response
    
    def is_production(self) -> bool:
        """Check if client is configured for production environment"""
        return self.config.is_production()
    
    def get_environment(self) -> str:
        """Get current environment (OTE or PRODUCTION)"""
        return self.config.godaddy_env
