# 🚀 Next.js Deployment & AWS Domain Manager

A streamlined Python toolkit for building, deploying, and managing domains on AWS.

## 🛠️ Key Services

### 1. Deployment Service
Build and deploy your Next.js application to AWS S3.

```python
from pathlib import Path
from src.services import DeploymentService

# Initialize with your project path
deployer = DeploymentService(Path("./my-app"))

# [Optional] Install dependencies before building
# Purpose: Runs 'pnpm install' (or any install command) inside app_directory
# Parameters: install_command (str, default: "pnpm install")
deployer.install_dependencies()
deployer.install_dependencies("npm ci")  # override command

# Build and upload to S3
# Purpose: Runs the build command then uploads the output directory to S3
# Parameters: bucket_name (str), make_public (bool), s3_prefix (str)
# Returns: { "bucket", "prefix", "region", "file_count", "files" }
deployer.build_and_deploy_s3(
    bucket_name="my-bucket-name",
    make_public=True
)
```

### 2. AWS Domain Service
Service for Route53 domain registration and automated DNS setup.

```python
from src.services import AWSDomainService

aws_dns = AWSDomainService()

# 1. Search for a domain
# Purpose: Check if a domain is available for registration
# Parameters: domain (str)
# Returns: { "domain", "available": bool, "message" }
result = aws_dns.check_availability("my-app.com")

# 2. Purchase a domain
# Purpose: Submit a registration request for a new domain
# Parameters: domain (str), contact_info (dict), duration_years (int, default 1)
# Returns: { "operation_id", "status" }
contact_info = {
    "FirstName": "Jane", "LastName": "Doe",
    "Email": "jane@example.com", "PhoneNumber": "+1.5551234567",
    "AddressLine1": "123 Main St", "City": "Austin",
    "State": "TX", "CountryCode": "US", "ZipCode": "78701"
}
result = aws_dns.register_domain("my-app.com", contact_info)

# 3. Write ACM validation CNAME records to Route53
# Purpose: After requesting an SSL cert, write the DNS records ACM needs to validate ownership
# Parameters: domain (str), validation_records (list of {"name", "value"} dicts)
# Returns: { "status": "success", "change_id" }
result = aws_dns.add_acm_dns_records("my-app.com", validation_records)

# 4. Point Route53 to CloudFront
# Purpose: Creates an Alias A record (root) and CNAME (www) pointing at a CloudFront distribution
# Parameters: domain (str), distribution_domain (str, e.g. "d123.cloudfront.net")
# Returns: { "status": "success", "hosted_zone_id", "change_id" }
result = aws_dns.setup_cloudfront_dns("my-app.com", "d123.cloudfront.net")
```

### 3. AWS CloudFront Service
Create CloudFront Distribution and point Route53 to CloudFront

```python
from src.services import AWSCloudFrontService

aws_cdn = AWSCloudFrontService()

# 1. Request SSL Certificate
# Purpose: Request a public DNS-validated SSL/TLS certificate from ACM (us-east-1)
# Parameters: domain (str), include_www (bool, default True)
# Returns: str — Certificate ARN
cert_arn = aws_cdn.request_ssl_certificate("my-app.com", include_www=True)
# → "arn:aws:acm:us-east-1:123456789012:certificate/abc-123"

# 2. Get ACM Validation DNS Records
# Purpose: Retrieve the CNAME records ACM needs to verify domain ownership.
#          Pass these to aws_dns.add_acm_dns_records() to write them to Route53.
# Parameters: cert_arn (str), timeout_seconds (int, default 60)
# Returns: list of { "name": str, "value": str }
validation_records = aws_cdn.get_acm_validation_records(cert_arn)

# 3. Wait for Certificate to be Issued
# Purpose: Block until the SSL cert status becomes ISSUED (DNS records must be in Route53 first)
# Parameters: cert_arn (str), timeout_minutes (int, default 30)
aws_cdn.wait_for_certificate(cert_arn, timeout_minutes=30)

# 4. Create CloudFront Distribution
# Purpose: Create a CloudFront distribution backed by an S3 static-website origin.
# When certificate_arn is supplied, HTTPS is enforced (redirect-to-https).
# Parameters: bucket_name (str), domain_name (str), certificate_arn (str, optional)
# Returns: { "distribution_id", "distribution_domain", "status", "arn" }
result = aws_cdn.create_s3_distribution(
    bucket_name="my-bucket-name",
    domain_name="my-app.com",
    certificate_arn=cert_arn,   # omit for HTTP-only
)
# → { "distribution_id": "E1ABCXYZ", "distribution_domain": "d123.cloudfront.net", ... }

# 5. Wait for Distribution to Deploy
# Purpose: Block until the CloudFront distribution status becomes "Deployed" (typically 15–20 min)
# Parameters: distribution_id (str), timeout_minutes (int, default 30)
aws_cdn.wait_for_distribution(result["distribution_id"], timeout_minutes=30)

```

### 4. Deployment Orchestrator
Runs all 9 steps in sequence with a single call — from build to a live HTTPS site.

```python
from pathlib import Path
from src.services import DeploymentOrchestrator

orch = DeploymentOrchestrator()

# Full pipeline: build → S3 upload → SSL cert → DNS validation → CloudFront → DNS → wait
# Purpose: Automates all steps end-to-end and returns the live URL
# Parameters:
#   app_dir (Path)                        — Next.js app directory
#   bucket_name (str)                     — S3 bucket name
#   domain (str)                          — Apex domain, e.g. "my-app.com"
#   install (bool, default False)         — Run pnpm install before building
#   build_command (str, default "pnpm build") — Override the build command
#   cert_timeout_minutes (int, default 30)    — Max wait for SSL cert issuance
#   distribution_timeout_minutes (int, default 30) — Max wait for CloudFront to deploy
# Returns: { "url", "distribution_id", "distribution_domain", "certificate_arn" }
result = orch.deploy_full(
    app_dir=Path("./my-app"),
    bucket_name="my-website-bucket",
    domain="my-app.com",
    install=True,
)

print(result["url"])  # https://my-app.com
```

### 🔐 Custom Configuration (Programmatic)
You can inject a custom configuration object into both services for one-time initialization.

```python
from src.utils.config import Settings
from src.services import DeploymentService, AWSDomainService

# 1. Define your configuration once
my_config = Settings(
    aws_access_key_id="YOUR_KEY",
    aws_secret_access_key="YOUR_SECRET",
    aws_region="us-east-1"
)

# 2. Inject it into the services
# Both services will now share the same credentials
deployer = DeploymentService(Path("./my-app"), config=my_config)
aws_dns = AWSDomainService(config=my_config)
aws_cdn = AWSCloudFrontService(config=my_config)
```

---

## 💻 CLI Usage

### Deploy App
```bash
# Standard deploy
python main.py deploy --app-dir ./my-app --s3 --s3-bucket my-bucket --public

# With dependency installation (runs 'pnpm install' first)
python main.py deploy --app-dir ./my-app --s3 --s3-bucket my-bucket --public --install
```

### Manage AWS Domains
```bash
# Search
python main.py aws-domain search my-app.com
```

### Manage AWS CloudFront (CDN)
```bash
# 1. Create CloudFront Distribution
python main.py aws-cdn create --bucket my-bucket --domain my-app.com

# 2. Setup DNS (Point Domain to CloudFront)
python main.py aws-domain setup-cdn-dns --domain my-app.com --cdn-domain d123.cloudfront.net
```

---

## ⚙️ Setup

Create a `.env` file in the root directory:

```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Domain Provider (Optional # methods not mentioned in document for now)
DOMAIN_PROVIDER=GODADDY
GODADDY_API_KEY=your_key
GODADDY_API_SECRET=your_secret
GODADDY_ENV=OTE
```

## 📦 Requirements
- Python 3.10+
- `pip install -r requirements.txt` (boto3, requests, pydantic)