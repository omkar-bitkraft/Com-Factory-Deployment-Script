"""
Example: Using the new Service Layer Architecture

This demonstrates how to use DeploymentService and DomainService
to build and deploy Next.js apps and manage domains.
"""

from pathlib import Path
from src.services import DeploymentService, DomainService
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Example 1: Build and Deploy Next.js App ====================

def example_deployment_local():
    """Example: Build and deploy Next.js app to local directory"""
    
    # Initialize deployment service with your Next.js app path
    app_directory = Path("c:/path/to/your/nextjs/app")
    deploy_service = DeploymentService(app_directory)
    
    # Option 1: Build and deploy in one call
    result = deploy_service.build_and_deploy_local(
        destination=Path("./output_files/deployment"),
        build_command="pnpm build",
        clean_destination=True,
        add_timestamp=False
    )
    
    print(f"Deployed to: {result}")
    
    # Option 2: Separate build and deploy steps
    # deploy_service.run_build("pnpm build")
    # deploy_service.deploy_local(Path("./output_files/deployment"))


def example_deployment_s3():
    """Example: Build and deploy Next.js app to S3"""
    
    app_directory = Path("c:/path/to/your/nextjs/app")
    deploy_service = DeploymentService(app_directory)
    
    result = deploy_service.build_and_deploy_s3(
        bucket_name="my-website-bucket",
        s3_prefix="production",  # Deploy to /production folder in S3
        build_command="pnpm build",
        make_public=True  # Make files publicly accessible
    )
    
    print(f"Deployed {result['file_count']} files to S3")
    print(f"Bucket: {result['bucket']}")
    print(f"Region: {result['region']}")


# ==================== Example 2: Domain Search and Management ====================

def example_domain_search():
    """Example: Search for available domains"""
    
    # Initialize domain service
    domain_service = DomainService()
    
    # Single domain search (with beautiful CLI display)
    result = domain_service.search_domain("myawesomeapp.com", display_results=True)
    
    if result["available"]:
        print(f"✅ {result['domain']} is available!")
        print(f"Price: ${result['price_dollars']:.2f}")
    else:
        print(f"❌ {result['domain']} is taken")
    
    # Multiple domain search
    domains_to_check = [
        "myapp.com",
        "myapp.net",
        "myapp.io",
        "my-awesome-app.com"
    ]
    
    results = domain_service.search_multiple_domains(
        domains_to_check,
        display_results=True  # Shows nice table
    )


def example_domain_suggestions():
    """Example: Get domain suggestions"""
    
    domain_service = DomainService()
    
    # Get suggestions based on keywords
    suggestions = domain_service.get_suggestions(
        query="coffee shop",
        limit=10,
        display_results=True
    )
    
    print(f"Found {len(suggestions)} suggestions")


def example_domain_purchase():
    """Example: Purchase a domain with validation workflow"""
    
    domain_service = DomainService()
    
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
    
    # Purchase with full validation workflow
    result = domain_service.purchase_domain_workflow(
        domain="test-purchase.com",
        contact_info=contact_info,
        period=1,  # 1 year
        privacy=False,
        validate_first=True,  # Validate before purchase
        confirm_purchase=True  # Require user confirmation
    )
    
    if result.get("status") == "cancelled":
        print("Purchase was cancelled")
    else:
        print(f"✅ Domain purchased! Order ID: {result.get('orderId')}")


def example_owned_domains():
    """Example: View domains in your account"""
    
    domain_service = DomainService()
    
    # Get owned domains (with beautiful table display)
    domains = domain_service.get_owned_domains(display_results=True)
    
    print(f"You own {len(domains)} domain(s)")
    
    # Get details for specific domain
    if domains:
        first_domain = domains[0].get("domain")
        details = domain_service.get_domain_info(
            first_domain,
            display_results=True
        )


# ==================== Example 3: Complete Workflow ====================

def example_complete_workflow():
    """
    Example: Complete workflow
    1. Search for domain
    2. Purchase domain if available
    3. Build Next.js app
    4. Deploy to S3
    5. Connect domain to deployment (manual DNS setup)
    """
    
    # Step 1: Search and purchase domain
    domain_service = DomainService()
    
    domain_name = "mynewwebsite.com"
    
    # Check availability
    result = domain_service.search_domain(domain_name)
    
    if not result["available"]:
        print(f"❌ Domain {domain_name} not available")
        return
    
    # Purchase domain
    contact_info = {
        "nameFirst": "John",
        "nameLast": "Doe",
        "email": "john@example.com",
        "phone": "+1.1234567890",
        "addressMailing": {
            "address1": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "postalCode": "94105",
            "country": "US"
        }
    }
    
    purchase_result = domain_service.purchase_domain_workflow(
        domain=domain_name,
        contact_info=contact_info,
        confirm_purchase=True
    )
    
    if purchase_result.get("status") == "cancelled":
        print("Workflow cancelled")
        return
    
    print(f"✅ Domain purchased: {domain_name}")
    
    # Step 2: Build and deploy app
    app_directory = Path("c:/path/to/nextjs/app")
    deploy_service = DeploymentService(app_directory)
    
    deploy_result = deploy_service.build_and_deploy_s3(
        bucket_name="my-website",
        s3_prefix=domain_name.replace(".", "-"),
        make_public=True
    )
    
    print(f"✅ Deployed {deploy_result['file_count']} files to S3")
    
    # Step 3: DNS setup (manual)
    print("\n📝 Next steps:")
    print(f"1. Configure DNS for {domain_name} to point to your S3 bucket")
    print(f"2. Set up CloudFront distribution (optional)")
    print(f"3. Configure SSL certificate")


# ==================== Run Examples ====================

if __name__ == "__main__":
    print("=" * 60)
    print("Service Layer Examples")
    print("=" * 60)
    
    # Uncomment to run examples:
    
    # Deployment examples
    # example_deployment_local()
    # example_deployment_s3()
    
    # Domain examples
    # example_domain_search()
    # example_domain_suggestions()
    # example_owned_domains()
    
    # Purchase (CAREFUL - uses real/test account)
    # example_domain_purchase()
    
    # Complete workflow
    # example_complete_workflow()
    
    print("\nExamples ready to run!")
    print("Uncomment the examples you want to try.")
