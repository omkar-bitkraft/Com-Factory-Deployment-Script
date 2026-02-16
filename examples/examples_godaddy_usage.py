"""
GoDaddy API Client - Usage Examples
====================================

This file demonstrates how to use the GoDaddy API client for various operations.

Prerequisites:
1. Configure .env file with your GoDaddy OTE credentials
2. Ensure GODADDY_ENV=OTE for testing
"""

from src.api import GoDaddyClient, APIError, DomainNotAvailableError
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Example 1: Initialize Client ====================

def example_initialize_client():
    """Initialize the GoDaddy API client"""
    client = GoDaddyClient()
    
    print(f"Environment: {client.get_environment()}")
    print(f"Base URL: {client.base_url}")
    print(f"Is Production: {client.is_production()}")
    
    return client


# ==================== Example 2: Check Domain Availability ====================

def example_check_availability():
    """Check if domains are available for purchase"""
    client = GoDaddyClient()
    
    domains_to_check = [
        "google.com",                           # Obviously taken
        "myawesomeuniquedomain12345.com",      # Probably available
        "test-domain-xyz.net"                   # Check various TLDs
    ]
    
    for domain in domains_to_check:
        try:
            result = client.check_availability(domain)
            
            available = result.get("available", False)
            print(f"\nDomain: {domain}")
            print(f"  Available: {available}")
            print(f"  Definitive: {result.get('definitive', False)}")
            
            if "price" in result:
                price_micros = result.get("price", 0)
                price_dollars = price_micros / 1_000_000
                currency = result.get("currency", "USD")
                period = result.get("period", 1)
                
                print(f"  Price: ${price_dollars:.2f} {currency} for {period} year(s)")
        
        except APIError as e:
            print(f"Error checking {domain}: {e}")


# ==================== Example 3: Get Domain Suggestions ====================

def example_domain_suggestions():
    """Get domain name suggestions based on keywords"""
    client = GoDaddyClient()
    
    queries = ["coffee shop", "tech startup", "photography"]
    
    for query in queries:
        try:
            suggestions = client.suggest_domains(query, limit=5)
            
            print(f"\nSuggestions for '{query}':")
            for i, domain in enumerate(suggestions, 1):
                print(f"  {i}. {domain}")
        
        except APIError as e:
            print(f"Error getting suggestions for '{query}': {e}")


# ==================== Example 4: Get Owned Domains ====================

def example_get_owned_domains():
    """Fetch all domains owned by your account"""
    client = GoDaddyClient()
    
    try:
        domains = client.get_domains()
        
        print(f"\nTotal domains in account: {len(domains)}")
        
        for domain_info in domains:
            domain_name = domain_info.get("domain", "N/A")
            status = domain_info.get("status", "N/A")
            created_at = domain_info.get("createdAt", "N/A")
            
            print(f"\nDomain: {domain_name}")
            print(f"  Status: {status}")
            print(f"  Created: {created_at}")
    
    except APIError as e:
        print(f"Error fetching domains: {e}")


# ==================== Example 5: Get Domain Details ====================

def example_get_domain_details():
    """Get detailed information about a specific domain"""
    client = GoDaddyClient()
    
    # First, get a domain from your account
    try:
        domains = client.get_domains()
        
        if not domains:
            print("No domains in account to get details for")
            return
        
        # Get details for first domain
        domain_name = domains[0].get("domain")
        details = client.get_domain_details(domain_name)
        
        print(f"\nDetails for {domain_name}:")
        print(f"  Domain ID: {details.get('domainId', 'N/A')}")
        print(f"  Status: {details.get('status', 'N/A')}")
        print(f"  Created: {details.get('createdAt', 'N/A')}")
        print(f"  Expires: {details.get('expires', 'N/A')}")
        print(f"  Auto Renew: {details.get('renewAuto', False)}")
        print(f"  Privacy: {details.get('privacy', False)}")
    
    except APIError as e:
        print(f"Error getting domain details: {e}")


# ==================== Example 6: Validate Domain Purchase ====================

def example_validate_purchase():
    """Validate a domain purchase without actually buying"""
    client = GoDaddyClient()
    
    domain = "test-validation-domain.com"
    
    # Contact information (required for purchase)
    contact_info = {
        "nameFirst": "John",
        "nameLast": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1.1234567890",
        "addressMailing": {
            "address1": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "postalCode": "94105",
            "country": "US"
        }
    }
    
    try:
        # First check if domain is available
        availability = client.check_availability(domain)
        
        if not availability.get("available"):
            print(f"Domain {domain} is not available")
            return
        
        # Validate the purchase
        validation = client.validate_purchase(domain, contact_info)
        
        print(f"\nValidation result for {domain}:")
        print(f"  Valid: {validation}")
    
    except DomainNotAvailableError:
        print(f"Domain {domain} is not available")
    except APIError as e:
        print(f"Error validating purchase: {e}")


# ==================== Example 7: Purchase Domain (CAREFUL!) ====================

def example_purchase_domain():
    """
    Purchase a domain (USE WITH CAUTION!)
    
    ⚠️  WARNING: This will actually purchase a domain if using PRODUCTION environment!
    ⚠️  Make sure you're in OTE (test) environment first!
    """
    client = GoDaddyClient()
    
    # Safety check
    if client.is_production():
        print("⚠️  DANGER: You're in PRODUCTION mode!")
        print("This will make a REAL purchase and charge your account!")
        response = input("Are you ABSOLUTELY sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Purchase cancelled for safety.")
            return
    
    domain = "test-purchase-domain-12345.com"
    
    # Contact information
    contact_info = {
        "nameFirst": "John",
        "nameLast": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1.1234567890",
        "addressMailing": {
            "address1": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "postalCode": "94105",
            "country": "US"
        }
    }
    
    try:
        # Check availability first
        availability = client.check_availability(domain)
        
        if not availability.get("available"):
            print(f"Domain {domain} is not available")
            return
        
        print(f"Domain {domain} is available!")
        print(f"Attempting purchase in {client.get_environment()} environment...")
        
        # Purchase the domain
        result = client.purchase_domain(
            domain=domain,
            contact_info=contact_info,
            period=1,              # 1 year
            privacy=False,         # Domain privacy
            auto_renew=False       # Auto-renewal
        )
        
        print(f"\n✅ Domain purchased successfully!")
        print(f"Order ID: {result.get('orderId', 'N/A')}")
        print(f"Total: ${result.get('total', 0) / 1_000_000:.2f}")
    
    except DomainNotAvailableError:
        print(f"❌ Domain {domain} is not available for purchase")
    except APIError as e:
        print(f"❌ Error purchasing domain: {e}")


# ==================== Example 8: Get Domain Schema ====================

def example_get_domain_schema():
    """Get the required schema for purchasing a domain with specific TLD"""
    client = GoDaddyClient()
    
    tlds = ["com", "net", "org", "io"]
    
    for tld in tlds:
        try:
            schema = client.get_domain_schema(tld)
            
            print(f"\nSchema for .{tld} domains:")
            print(f"  Required: {schema.get('required', [])}")
            
        except APIError as e:
            print(f"Error getting schema for .{tld}: {e}")


# ==================== Example 9: Error Handling ====================

def example_error_handling():
    """Demonstrate proper error handling"""
    client = GoDaddyClient()
    
    try:
        # Try to get details for a domain that doesn't exist
        details = client.get_domain_details("this-domain-does-not-exist-in-my-account.com")
        print(details)
        
    except DomainNotAvailableError as e:
        print(f"Domain not found: {e}")
        print(f"Status code: {e.status_code}")
        
    except APIError as e:
        print(f"API error: {e}")
        print(f"Status code: {e.status_code}")
        print(f"Response data: {e.response_data}")


# ==================== Main ====================

def main():
    """Run all examples"""
    print("=" * 60)
    print("GoDaddy API Client - Usage Examples")
    print("=" * 60)
    
    # Example 1: Initialize
    print("\n\n--- Example 1: Initialize Client ---")
    client = example_initialize_client()
    
    # Example 2: Check availability
    print("\n\n--- Example 2: Check Domain Availability ---")
    example_check_availability()
    
    # Example 3: Domain suggestions
    print("\n\n--- Example 3: Domain Suggestions ---")
    example_domain_suggestions()
    
    # Example 4: Get owned domains
    print("\n\n--- Example 4: Get Owned Domains ---")
    example_get_owned_domains()
    
    # Uncomment to run other examples:
    # example_get_domain_details()
    # example_validate_purchase()
    # example_get_domain_schema()
    # example_error_handling()
    
    # ⚠️  DANGER: Only run this in OTE environment!
    # example_purchase_domain()


if __name__ == "__main__":
    main()
