"""
Domain Provider Factory
Creates domain provider instances based on configuration
"""

from typing import Optional

from src.api.base_provider import BaseDomainProvider
from src.api.godaddy_client import GoDaddyClient
from src.api.dnsimple_client import DNSimpleClient
from src.utils.config import get_settings, Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_domain_provider(
    provider_name: Optional[str] = None,
    config: Optional[Settings] = None
) -> BaseDomainProvider:
    """
    Factory function to create domain provider instances.
    
    Args:
        provider_name: Optional provider name ("GODADDY" or "DNSIMPLE").
                      If None, reads from config.
        config: Optional Settings instance. Uses default if None.
        
    Returns:
        Domain provider instance
        
    Raises:
        ValueError: If provider_name is invalid
        
    Example:
        # Use configured provider
        provider = get_domain_provider()
        
        # Explicitly use DNSimple
        provider = get_domain_provider("DNSIMPLE")
        
        # Use GoDaddy
        provider = get_domain_provider("GODADDY")
    """
    if config is None:
        config = get_settings()
    
    # Determine provider
    if provider_name is None:
        provider_name = config.domain_provider
    
    provider_name = provider_name.upper()
    
    logger.info(f"Creating domain provider: {provider_name}")
    
    # Create provider instance
    if provider_name == "GODADDY":
        return GoDaddyClient(config)
    
    elif provider_name == "DNSIMPLE":
        return DNSimpleClient(config)
    
    else:
        raise ValueError(
            f"Unknown domain provider: {provider_name}. "
            f"Valid options are: GODADDY, DNSIMPLE"
        )
