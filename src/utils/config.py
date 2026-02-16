"""
Configuration management using Pydantic Settings
Loads and validates environment variables from .env file
"""

from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Environment-agnostic: supports both OTE (test) and PRODUCTION
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # GoDaddy API Configuration
    godaddy_api_key: str = Field(
        ...,
        description="GoDaddy API Key"
    )
    godaddy_api_secret: str = Field(
        ...,
        description="GoDaddy API Secret"
    )
    godaddy_env: Literal["OTE", "PRODUCTION"] = Field(
        default="OTE",
        description="GoDaddy environment: OTE (test) or PRODUCTION"
    )
    
    # Domain Provider Selection
    domain_provider: Literal["GODADDY", "DNSIMPLE"] = Field(
        default="GODADDY",
        description="Domain provider to use: GODADDY or DNSIMPLE"
    )
    
    # DNSimple API Configuration
    dnsimple_api_token: str = Field(
        default="",
        description="DNSimple API token"
    )
    dnsimple_account_id: str = Field(
        default="",
        description="DNSimple account ID"
    )
    dnsimple_sandbox: bool = Field(
        default=True,
        description="Use DNSimple sandbox environment"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    # AWS S3 Configuration (Optional)
    aws_access_key_id: str = Field(
        default="",
        description="AWS Access Key ID for S3 deployment"
    )
    aws_secret_access_key: str = Field(
        default="",
        description="AWS Secret Access Key for S3 deployment"
    )
    aws_s3_bucket: str = Field(
        default="",
        description="AWS S3 bucket name for deployment"
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region"
    )
    
    @property
    def godaddy_base_url(self) -> str:
        """
        Returns the appropriate GoDaddy API base URL based on environment
        """
        if self.godaddy_env == "OTE":
            return "https://api.ote-godaddy.com"
        return "https://api.godaddy.com"
    
    @property
    def godaddy_auth_header(self) -> dict:
        """
        Returns the authorization header for GoDaddy API requests
        """
        return {
            "Authorization": f"sso-key {self.godaddy_api_key}:{self.godaddy_api_secret}"
        }
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper
    
    @field_validator("godaddy_api_key", "godaddy_api_secret")
    @classmethod
    def validate_godaddy_credentials(cls, v: str, info) -> str:
        """Validate GoDaddy credentials only if GoDaddy is the selected provider"""
        # Skip validation if DNSimple is the provider
        if hasattr(info.data, 'get'):
            provider = info.data.get('domain_provider', 'GODADDY')
            if provider == 'DNSIMPLE':
                return v or ""
        
        # Validate for GoDaddy
        if not v or v == "your_api_key_here" or v == "your_api_secret_here":
            raise ValueError(
                "GoDaddy API credentials must be set in .env file when using GODADDY provider. "
                "Copy .env.example to .env and add your actual credentials."
            )
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        if self.domain_provider == "DNSIMPLE":
            return not self.dnsimple_sandbox
        return self.godaddy_env == "PRODUCTION"
    
    def has_aws_config(self) -> bool:
        """Check if AWS S3 configuration is complete"""
        return bool(
            self.aws_access_key_id 
            and self.aws_secret_access_key 
            and self.aws_s3_bucket
        )


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get or create the settings singleton instance.
    Loads configuration from .env file on first call.
    
    Returns:
        Settings instance
        
    Raises:
        FileNotFoundError: If .env file doesn't exist
        ValidationError: If required environment variables are missing or invalid
    """
    global _settings
    
    if _settings is None:
        # Check if .env file exists
        env_file = Path(".env")
        if not env_file.exists():
            raise FileNotFoundError(
                ".env file not found. Please copy .env.example to .env and "
                "configure your GoDaddy API credentials."
            )
        
        _settings = Settings()
    
    return _settings


def reset_settings():
    """
    Reset the settings singleton (useful for testing)
    """
    global _settings
    _settings = None
