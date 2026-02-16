"""
API Layer - Domain Provider Implementations
Supports multiple domain providers with unified interface
"""

# Base Provider
from src.api.base_provider import BaseDomainProvider

# Provider Implementations
from src.api.godaddy_client import GoDaddyClient
from src.api.dnsimple_client import DNSimpleClient

# Provider Factory
from src.api.provider_factory import get_domain_provider

# Exceptions (shared across providers)
from src.api.exceptions import (
    APIError,
    AuthenticationError,
    DomainNotAvailableError,
    DomainNotFoundError,
    InsufficientFundsError,
    RateLimitError,
    InvalidDomainError,
    ValidationError,
    NetworkError,
    ServerError
)

__all__ = [
    # Base
    "BaseDomainProvider",
    
    # Providers
    "GoDaddyClient",
    "DNSimpleClient",
    
    # Factory
    "get_domain_provider",
    
    # Exceptions
    "APIError",
    "AuthenticationError",
    "DomainNotAvailableError",
    "DomainNotFoundError",
    "InsufficientFundsError",
    "RateLimitError",
    "InvalidDomainError",
    "ValidationError",
    "NetworkError",
    "ServerError"
]
