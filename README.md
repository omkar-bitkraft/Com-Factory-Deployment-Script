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

# Build and upload to S3
deployer.build_and_deploy_s3(
    bucket_name="my-bucket-name",
    make_public=True
)
```

### 2. AWS Domain Service
Standalone service for Route53 domain registration and automated DNS setup.

```python
from src.services import AWSDomainService

aws_dns = AWSDomainService()

# 1. Search for a domain
result = aws_dns.check_availability("my-app.com")
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
```

---

## 💻 CLI Usage

### Deploy App
```bash
python main.py deploy --app-dir ./my-app --s3 --s3-bucket my-bucket --public
```

### Manage AWS Domains
```bash
# Search
python main.py aws-domain search my-app.com
```

---

## ⚙️ Setup

Create a `.env` file in the root directory:

```env
# AWS Credentials
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Domain Provider (Optional)
DOMAIN_PROVIDER=GODADDY
GODADDY_API_KEY=your_key
GODADDY_API_SECRET=your_secret
GODADDY_ENV=OTE
```

## 📦 Requirements
- Python 3.10+
- `pip install -r requirements.txt` (boto3, requests, pydantic)