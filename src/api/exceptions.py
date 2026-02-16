"""
Custom exceptions for GoDaddy API operations
"""


class APIError(Exception):
    """Base exception for all API errors"""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.status_code:
            return f"APIError (HTTP {self.status_code}): {self.message}"
        return f"APIError: {self.message}"


class AuthenticationError(APIError):
    """Raised when API authentication fails"""
    pass


class DomainNotAvailableError(APIError):
    """Raised when a domain is not available for purchase"""
    pass


class DomainNotFoundError(APIError):
    """Raised when a domain is not found in user's account"""
    pass


class InsufficientFundsError(APIError):
    """Raised when account has insufficient funds for purchase"""
    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded"""
    pass


class InvalidDomainError(APIError):
    """Raised when domain format is invalid"""
    pass


class NetworkError(APIError):
    """Raised when network/connection errors occur"""
    pass


class ValidationError(APIError):
    """Raised when request validation fails"""
    pass


class ServerError(APIError):
    """Raised when GoDaddy server returns 5xx errors"""
    pass

class NotImplementedError(APIError):
    """Raised when a method is not implemented in the provider"""
    pass
