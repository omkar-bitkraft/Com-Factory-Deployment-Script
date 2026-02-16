"""
Input validation utilities for domains, emails, and other user input
"""

import re
from typing import Optional


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class DomainValidator:
    """Validator for domain names"""
    
    # RFC-compliant domain regex
    DOMAIN_REGEX = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    
    # Simple domain regex (allows subdomain-less domains)
    SIMPLE_DOMAIN_REGEX = re.compile(
        r'^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]$'
    )
    
    @classmethod
    def validate(cls, domain: str, allow_subdomain: bool = True) -> str:
        """
        Validate a domain name.
        
        Args:
            domain: Domain name to validate
            allow_subdomain: Whether to allow subdomains
            
        Returns:
            Cleaned domain name (lowercase, stripped)
            
        Raises:
            ValidationError: If domain is invalid
        """
        if not domain:
            raise ValidationError("Domain name cannot be empty")
        
        # Clean the domain
        domain = domain.strip().lower()
        
        # Remove http(s):// if present
        domain = re.sub(r'^https?://', '', domain)
        
        # Remove trailing slash
        domain = domain.rstrip('/')
        
        # Check length
        if len(domain) > 253:  # RFC 1035
            raise ValidationError("Domain name too long (max 253 characters)")
        
        # Check format
        if allow_subdomain:
            if not cls.DOMAIN_REGEX.match(domain):
                # Try without subdomain
                if not cls.SIMPLE_DOMAIN_REGEX.match(domain.split('.')[0]):
                    raise ValidationError(
                        f"Invalid domain format: {domain}. "
                        "Domain must contain only letters, numbers, and hyphens."
                    )
        else:
            if not cls.SIMPLE_DOMAIN_REGEX.match(domain):
                raise ValidationError(
                    f"Invalid domain format: {domain}. "
                    "Domain must contain only letters, numbers, and hyphens."
                )
        
        return domain
    
    @classmethod
    def extract_tld(cls, domain: str) -> str:
        """
        Extract TLD from domain name.
        
        Args:
            domain: Domain name
            
        Returns:
            TLD (e.g., 'com', 'org', 'co.uk')
        """
        parts = domain.split('.')
        if len(parts) < 2:
            return ""
        return parts[-1]
    
    @classmethod
    def extract_sld(cls, domain: str) -> str:
        """
        Extract Second-Level Domain (SLD) from domain name.
        
        Args:
            domain: Domain name (e.g., 'example.com')
            
        Returns:
            SLD (e.g., 'example')
        """
        parts = domain.split('.')
        if len(parts) < 2:
            return domain
        return parts[-2]


class EmailValidator:
    """Validator for email addresses"""
    
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    @classmethod
    def validate(cls, email: str) -> str:
        """
        Validate an email address.
        
        Args:
            email: Email address to validate
            
        Returns:
            Cleaned email address (lowercase, stripped)
            
        Raises:
            ValidationError: If email is invalid
        """
        if not email:
            raise ValidationError("Email address cannot be empty")
        
        email = email.strip().lower()
        
        if not cls.EMAIL_REGEX.match(email):
            raise ValidationError(f"Invalid email format: {email}")
        
        return email


class PhoneValidator:
    """Validator for phone numbers"""
    
    # Basic international phone number regex
    PHONE_REGEX = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    @classmethod
    def validate(cls, phone: str) -> str:
        """
        Validate and clean a phone number.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            Cleaned phone number
            
        Raises:
            ValidationError: If phone number is invalid
        """
        if not phone:
            raise ValidationError("Phone number cannot be empty")
        
        # Remove common separators
        phone = re.sub(r'[\s\-\(\)\.]+', '', phone.strip())
        
        if not cls.PHONE_REGEX.match(phone):
            raise ValidationError(
                f"Invalid phone format: {phone}. "
                "Use international format (e.g., +12345678901)"
            )
        
        return phone


def validate_domain(domain: str) -> str:
    """Convenience function for domain validation"""
    return DomainValidator.validate(domain)


def validate_email(email: str) -> str:
    """Convenience function for email validation"""
    return EmailValidator.validate(email)


def validate_phone(phone: str) -> str:
    """Convenience function for phone validation"""
    return PhoneValidator.validate(phone)
