"""
Base Domain Provider Interface
Abstract base class for domain provider implementations
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseDomainProvider(ABC):
    """
    Abstract base class for domain providers.
    All domain provider implementations must inherit this class.
    """
    
    @abstractmethod
    def get_environment(self) -> str:
        """
        Get current environment (OTE/Sandbox or Production).
        
        Returns:
            Environment name string
        """
        pass
    
    @abstractmethod
    def is_production(self) -> bool:
        """
        Check if running in production environment.
        
        Returns:
            True if production, False if test/sandbox
        """
        pass
    
    @abstractmethod
    def check_availability(self, domain: str) -> Dict[str, Any]:
        """
        Check if domain is available for purchase.
        
        Args:
            domain: Domain name to check
            
        Returns:
            Dictionary with availability info:
            {
                "available": bool,
                "domain": str,
                "price": int (micros) or float,
                "expiresAt": str (ISO date) or None,
                "currency": str,
                "period": int
            }
        """
        pass
    
    @abstractmethod
    def suggest_domains(self, query: str, limit: int = 10) -> List[str]:
        """
        Get domain name suggestions.
        
        Args:
            query: Search query/keywords
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested domain names
        """
        pass
    
    @abstractmethod
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
            contact_info: Contact/registrant information
            period: Registration period in years
            privacy: Enable domain privacy
            auto_renew: Enable auto-renewal
            
        Returns:
            Purchase result dictionary
        """
        pass
    
    @abstractmethod
    def get_domains(self) -> List[Dict[str, Any]]:
        """
        Get list of owned domains.
        
        Returns:
            List of domain dictionaries
        """
        pass
    
    @abstractmethod
    def get_domain_details(self, domain: str) -> Dict[str, Any]:
        """
        Get detailed information about a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Domain details dictionary
        """
        pass
    
    @abstractmethod
    def validate_purchase(
        self,
        domain: str,
        contact_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate domain purchase without actually buying.
        
        Args:
            domain: Domain to validate
            contact_info: Contact information
            
        Returns:
            Validation result
        """
        pass
    
    def get_provider_name(self) -> str:
        """
        Get provider name.
        Default implementation returns class name.
        
        Returns:
            Provider name string
        """
        return self.__class__.__name__.replace("Client", "")
