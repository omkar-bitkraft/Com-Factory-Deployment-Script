"""
Main CLI Entry Point
Unified command-line interface for:
- Next.js build and deployment
- GoDaddy domain management
"""

import sys
import argparse
from pathlib import Path

from src.services import DeploymentService, DomainService, AWSDomainService, AWSCDNService
from src.utils.logger import get_logger
from src.utils.config import Settings

logger = get_logger(__name__)


def cmd_build_deploy(args):
    """Build and deploy Next.js application"""
    logger.info(f"Starting build & deploy: {args.app_dir}")
    
    try:
        deploy_service = DeploymentService(Path(args.app_dir))
        
        if hasattr(args, 'install') and args.install:
            deploy_service.install_dependencies()
        
        if args.s3:
            # S3 deployment
            result = deploy_service.build_and_deploy_s3(
                bucket_name=args.s3_bucket,
                s3_prefix=args.s3_prefix or "",
                build_command=args.build_cmd,
                make_public=args.public
            )
            logger.info(f"\u2705 Deployed {result['file_count']} files to S3: {result['bucket']}")
        else:
            # Local deployment
            destination = Path(args.output) if args.output else Path("./output_files/deployment")
            result = deploy_service.build_and_deploy_local(
                destination=destination,
                build_command=args.build_cmd,
                clean_destination=not args.no_clean,
                add_timestamp=args.timestamp
            )
            logger.info(f"\u2705 Deployed to: {result}")
    
    except Exception as e:
        logger.error(f"\u274c Deployment failed: {str(e)}")
        sys.exit(1)


def cmd_domain_search(args):
    """Search for domain availability"""
    logger.info(f"Searching domain: {args.domain}")
    
    try:
        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        
        if args.multiple:
            # Multiple domains
            domains = args.domain.split(",")
            results = domain_service.search_multiple_domains(domains)
            
            # Print summary
            print(f"\n{'='*60}")
            print(f" DOMAIN SEARCH RESULTS ({len(results)} domains)")
            print(f"{'='*60}")
            for result in results:
                status = "\u2705 AVAILABLE" if result.get("available") else "\u274c TAKEN"
                price = f"${result.get('price', 0):.2f}" if result.get("available") else "-"
                print(f"  {result['domain']:<40} {status:15} {price}")
            print(f"{'='*60}\n")
        else:
            # Single domain
            result = domain_service.search_domain(args.domain)
            
            # Print result
            print(f"\n{'='*60}")
            print(f" DOMAIN: {result['domain']}")
            print(f"{'='*60}")
            print(f"  Available: {'YES \u2705' if result['available'] else 'NO \u274c'}")
            if result['available']:
                print(f"  Price:        ${result['price']:.2f} {result['currency']}")
                print(f"  Period:       {result['period']} year(s)")
                print(f"  Expires At:   {result['expires_at']} ")
            print(f"{'='*60}\n")
    
    except Exception as e:
        logger.error(f"\u274c Domain search failed: {str(e)}")
        sys.exit(1)


def cmd_domain_suggest(args):
    """Get domain suggestions"""
    logger.info(f"Getting suggestions for: {args.query}")
    
    try:
        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        suggestions = domain_service.get_suggestions(args.query, limit=args.limit)
        
        # Print suggestions
        print(f"\n{'='*60}")
        print(f" DOMAIN SUGGESTIONS FOR: '{args.query}'")
        print(f"{'='*60}")
        for i, domain in enumerate(suggestions, 1):
            print(f"  {i:2}. {domain}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        logger.error(f"\u274c Failed to get suggestions: {str(e)}")
        sys.exit(1)


def cmd_domain_list(args):
    """List owned domains"""
    logger.info("Fetching owned domains...")
    
    try:
        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        domains = domain_service.get_owned_domains()
        
        # Print domains
        print(f"\n{'='*60}")
        print(f" OWNED DOMAINS ({len(domains)})")
        print(f"{'='*60}")
        for domain_info in domains:
            domain_name = domain_info.get("domain", "N/A")
            status = domain_info.get("status", "N/A")
            created = domain_info.get("createdAt", "N/A")[:10] if domain_info.get("createdAt") else "N/A"
            print(f"  {domain_name:<40} Status: {status:<15} Created: {created}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        logger.error(f"\u274c Failed to fetch domains: {str(e)}")
        sys.exit(1)


def cmd_domain_info(args):
    """Get domain details"""
    logger.info(f"Getting details for: {args.domain}")
    
    try:
        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        details = domain_service.get_domain_info(args.domain)
        
        # Print details
        print(f"\n{'='*60}")
        print(f" DOMAIN DETAILS: {details.get('domain', 'N/A')}")
        print(f"{'='*60}")
        print(f"  Status:      {details.get('status', 'N/A')}")
        print(f"  Created:     {details.get('createdAt', 'N/A')}")
        print(f"  Expires:     {details.get('expires', 'N/A')}")
        print(f"  Auto-Renew:  {details.get('renewAuto', False)}")
        print(f"  Privacy:     {details.get('privacy', False)}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        logger.error(f"\u274c Failed to get domain details: {str(e)}")
        sys.exit(1)

import json

def cmd_domain_purchase(args):
    """Purchase a domain, with necessary arguments and contact info"""
    logger.info(f"Purchasing domain: {args.domain}")

    try:
        contact_info = None
        if args.contact_info:
            try:
                contact_info = json.loads(args.contact_info)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid contact-info JSON: {str(e)}")
                sys.exit(1)

        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        #TODO: contact-info to be validate what to be sent, along with "registrant_id" how to generate via API also which is in the below method itself
        purchase_result = domain_service.purchase_domain_workflow(
            domain=args.domain,
            contact_info=contact_info,
            period=args.period if hasattr(args, 'period') else 1,
            privacy=args.privacy if hasattr(args, 'privacy') else False,
            auto_renew=args.auto_renew if hasattr(args, 'auto_renew') else False
        )
        logger.info(f"Purchase result: {purchase_result}")
    except Exception as e:
        logger.error(f"Failed to purchase domain: {str(e)}")
        sys.exit(1)

def cmd_contact_info(args):
    """Get contact/registrant information for the account"""
    logger.info("Fetching contact information...")
    
    try:
        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        contact_info = domain_service.get_contact_info()
        
        # Print contact info
        print(f"\n{'='*60}")
        print(f" CONTACT INFORMATION")
        print(f"{'='*60}")
        if isinstance(contact_info, list):
            for contact in contact_info:
                for key, value in contact.items():
                    print(f"  {key.capitalize()}: {value}")
        else:
            for key, value in contact_info.items():
                print(f"  {key.capitalize()}: {value}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        logger.error(f"\u274c Failed to fetch contact information: {str(e)}")
        sys.exit(1)

def cmd_contact_create(args):
    """Create contact/registrant information"""
    logger.info("Creating contact information...")
    
    try:
        contact_info = None
        if args.contact_info:
            try:
                contact_info = json.loads(args.contact_info)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid contact-info JSON: {str(e)}")
                sys.exit(1)
        # Ensure contact info is provided
        if not contact_info:
             logger.error("Contact info is required for contact creation. Please provide --contact-info as a JSON string.")
             sys.exit(1)
        domain_service = DomainService(provider_name=args.provider if hasattr(args, 'provider') else None)
        contact_info = domain_service.create_contact_info(contact_info)
        logger.info(f"Contact information created: {contact_info}")
    except Exception as e:
        logger.error(f"\u274c Failed to create contact information: {str(e)}")
        sys.exit(1)

def cmd_aws_domain_search(args):
    """Search for domain availability on AWS"""
    logger.info(f"Searching AWS domain: {args.domain}")
    
    try:
        custom_config = Settings()
        aws_service = AWSDomainService(config=custom_config)
        result = aws_service.check_availability(args.domain)
        
        # Print result
        print(f"\n{'='*60}")
        print(f" AWS DOMAIN: {result['domain']}")
        print(f"{'='*60}")
        print(f"  Available: {'YES \u2705' if result['available'] else 'NO \u274c'}")
        print(f"  Status:    {result['status']}")
        
        if result['available']:
            suggestions = aws_service.get_suggestions(args.domain)
            if suggestions:
                print(f"\n  Suggestions:")
                for s in suggestions[:5]:
                    print(f"    - {s}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        logger.error(f"\u274c AWS Domain search failed: {str(e)}")
        sys.exit(1)


def cmd_aws_domain_register(args):
    """Register a domain on AWS"""
    logger.info(f"Registering AWS domain: {args.domain}")
    
    try:
        contact_info = None
        if args.contact:
            with open(args.contact, 'r') as f:
                contact_info = json.load(f)
        else:
            logger.error("Contact info file (--contact) is required for AWS registration.")
            sys.exit(1)
            
        aws_service = AWSDomainService()
        result = aws_service.register_domain(
            domain=args.domain,
            contact_info=contact_info,
            duration=args.duration
        )
        
        print(f"\n{'='*60}")
        print(f" AWS REGISTRATION SUBMITTED")
        print(f"{'='*60}")
        print(f"  Domain:       {result['domain']}")
        print(f"  Operation ID: {result['operation_id']}")
        print(f"  Status:       {result['status']}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"\u274c AWS Registration failed: {str(e)}")
        sys.exit(1)


def cmd_aws_cdn_create(args):
    """Create CloudFront distribution for S3 bucket"""
    logger.info(f"Creating CloudFront distribution for bucket: {args.bucket}")
    
    try:
        # Initialize with settings
        aws_cdn = AWSCDNService(config=Settings())
        
        result = aws_cdn.create_s3_distribution(
            bucket_name=args.bucket,
            domain_name=args.domain
        )
        
        print(f"\n{'='*60}")
        print(f" CLOUDFRONT DISTRIBUTION CREATED")
        print(f"{'='*60}")
        print(f"  ID:          {result['distribution_id']}")
        print(f"  Domain:      {result['distribution_domain']}")
        print(f"  Status:      {result['status']}")
        print(f"  ARN:         {result['arn']}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"\u274c Failed to create distribution: {str(e)}")
        sys.exit(1)


def cmd_aws_domain_setup_cdn_dns(args):
    """Setup Route53 DNS for CloudFront distribution"""
    logger.info(f"Setting up DNS for {args.domain} -> {args.cdn_domain}")
    
    try:
        # Initialize with settings
        aws_service = AWSDomainService(config=Settings())
        result = aws_service.setup_cloudfront_dns(
            domain=args.domain,
            distribution_domain=args.cdn_domain
        )
        
        print(f"\n{'='*60}")
        print(f" AWS DNS SETUP COMPLETE")
        print(f"{'='*60}")
        print(f"  Domain:      {args.domain}")
        print(f"  Target:      {args.cdn_domain}")
        print(f"  Hosted Zone: {result['hosted_zone_id']}")
        print(f"  Change ID:   {result['change_id']}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"\u274c AWS DNS setup failed: {str(e)}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Next.js Deployment & Domain Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build and deploy locally
  python main.py deploy --app-dir ./my-nextjs-app --output ./deployment
  
  # Build and deploy to S3
  python main.py deploy --app-dir ./my-nextjs-app --s3 --s3-bucket my-bucket --public
  
  # Search domain
  python main.py domain search myawesomeapp.com
  
  # Search multiple domains
  python main.py domain search "app.com,app.net,app.io" --multiple
  
  # Get domain suggestions
  python main.py domain suggest "coffee shop" --limit 10
  
  # List owned domains
  python main.py domain list
  
  # Get domain details
  python main.py domain info myexistingdomain.com

  # Get contact details
  python main.py contact-info

  # Create contact
  python main.py contact-create '{"name": "John Doe", "email": "john@example.com"}'

  # Purchase a domain
  python main.py domain purchase mynewdomain.com --contact-info '{"name": "John Doe", "email": "john@example.com"}' --period 2 --privacy --auto-renew
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ==================== DEPLOY COMMAND ====================
    deploy_parser = subparsers.add_parser("deploy", help="Build and deploy Next.js app")
    deploy_parser.add_argument("--app-dir", required=True, help="Path to Next.js application")
    deploy_parser.add_argument("--output", help="Local deployment directory (default: ./output_files/deployment)")
    deploy_parser.add_argument("--build-cmd", default="pnpm build", help="Build command (default: pnpm build)")
    deploy_parser.add_argument("--no-clean", action="store_true", help="Don't clean destination before deployment")
    deploy_parser.add_argument("--timestamp", action="store_true", help="Add timestamp to deployment folder")
    deploy_parser.add_argument("--install", action="store_true", help="Run 'pnpm install' before building")
    
    # S3 options
    deploy_parser.add_argument("--s3", action="store_true", help="Deploy to AWS S3")
    deploy_parser.add_argument("--s3-bucket", help="S3 bucket name")
    deploy_parser.add_argument("--s3-prefix", help="S3 prefix (folder path)")
    deploy_parser.add_argument("--public", action="store_true", help="Make S3 files public")
    deploy_parser.set_defaults(func=cmd_build_deploy)
    
    # ==================== DOMAIN COMMAND ====================
    domain_parser = subparsers.add_parser("domain", help="Domain management")
    domain_subparsers = domain_parser.add_subparsers(dest="domain_command", help="Domain operations")
    
    # domain search
    search_parser = domain_subparsers.add_parser("search", help="Search domain availability")
    search_parser.add_argument("domain", help="Domain name (or comma-separated for multiple)")
    search_parser.add_argument("--multiple", action="store_true", help="Search multiple domains")
    search_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    search_parser.set_defaults(func=cmd_domain_search)
    
    # domain suggest
    suggest_parser = domain_subparsers.add_parser("suggest", help="Get domain suggestions")
    suggest_parser.add_argument("query", help="Search query")
    suggest_parser.add_argument("--limit", type=int, default=10, help="Max suggestions (default: 10)")
    suggest_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    suggest_parser.set_defaults(func=cmd_domain_suggest)
    
    # domain list
    list_parser = domain_subparsers.add_parser("list", help="List owned domains")
    list_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    list_parser.set_defaults(func=cmd_domain_list)
    
    # domain info
    info_parser = domain_subparsers.add_parser("info", help="Get domain details")
    info_parser.add_argument("domain", help="Domain name")
    info_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    info_parser.set_defaults(func=cmd_domain_info)

    # domain purchase
    purchase_parser = domain_subparsers.add_parser("purchase", help="Purchase a domain")
    purchase_parser.add_argument("domain", help="Domain name to purchase")
    purchase_parser.add_argument("--contact-info", type=str, help="Registrant contact info as JSON string")
    purchase_parser.add_argument("--period", type=int, default=1, help="Registration period in years (default: 1)")
    purchase_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    purchase_parser.set_defaults(func=cmd_domain_purchase)

    # contact info
    contact_parser = subparsers.add_parser("contact-info", help="Get contact/registrant information")
    contact_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    contact_parser.set_defaults(func=cmd_contact_info)

    # contact create
    contact_parser = subparsers.add_parser("contact-create", help="Create contact/registrant information")
    #Also suggest the necessary keys required for contact creation
    contact_parser.add_argument("--contact-info", type=str, help="Registrant contact info as JSON string (required keys: nameFirst, nameLast, email, phone, addressMailing, city, state, postalCode, country)")
    contact_parser.add_argument("--provider", choices=["GODADDY", "DNSIMPLE"], help="Domain provider (default: from config)")
    contact_parser.set_defaults(func=cmd_contact_create)

    # ==================== AWS CDN COMMAND ====================
    aws_cdn_parser = subparsers.add_parser("aws-cdn", help="AWS CloudFront management")
    aws_cdn_subparsers = aws_cdn_parser.add_subparsers(dest="aws_cdn_command", help="AWS CDN operations")
    
    # aws-cdn create
    cdn_create_parser = aws_cdn_subparsers.add_parser("create", help="Create CloudFront distribution")
    cdn_create_parser.add_argument("--bucket", required=True, help="S3 bucket name")
    cdn_create_parser.add_argument("--domain", required=True, help="Custom domain name")
    cdn_create_parser.set_defaults(func=cmd_aws_cdn_create)

    # ==================== AWS DOMAIN COMMAND ====================
    aws_domain_parser = subparsers.add_parser("aws-domain", help="AWS Route53 domain management (Standalone)")
    aws_domain_subparsers = aws_domain_parser.add_subparsers(dest="aws_domain_command", help="AWS Domain operations")

    # aws-domain search
    aws_search_parser = aws_domain_subparsers.add_parser("search", help="Search domain availability on AWS")
    aws_search_parser.add_argument("domain", help="Domain name")
    aws_search_parser.set_defaults(func=cmd_aws_domain_search)

    # aws-domain register
    aws_register_parser = aws_domain_subparsers.add_parser("register", help="Register a domain on AWS")
    aws_register_parser.add_argument("domain", help="Domain name")
    aws_register_parser.add_argument("--contact", required=True, help="Path to contact JSON file")
    aws_register_parser.add_argument("--duration", type=int, default=1, help="Registration period (years)")
    aws_register_parser.set_defaults(func=cmd_aws_domain_register)

    # aws-domain setup-cdn-dns
    aws_dns_parser = aws_domain_subparsers.add_parser("setup-cdn-dns", help="Setup Route53 DNS for CloudFront")
    aws_dns_parser.add_argument("--domain", required=True, help="Domain name")
    aws_dns_parser.add_argument("--cdn-domain", required=True, help="CloudFront domain (e.g., d123.cloudfront.net)")
    aws_dns_parser.set_defaults(func=cmd_aws_domain_setup_cdn_dns)

    
    # Parse and execute
    args = parser.parse_args()
    
    if not args.command:
        # run the search domain for now since want to debug and not able to run by command
        # args = parser.parse_args(["domain", "search", "myawesomeuniquedomain12345.com"])
        # cmd_domain_search(args)
        # sys.exit(1)
        parser.print_help()
        sys.exit(0)
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()