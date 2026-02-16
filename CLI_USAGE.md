# CLI Usage Guide

## Quick Start

### Deploy Commands

**Build and deploy locally:**
```bash
python main.py deploy --app-dir ./my-nextjs-app --output ./deployment
```

**Build and deploy to S3:**
```bash
python main.py deploy --app-dir ./my-nextjs-app --s3 --s3-bucket my-bucket --public
```

### Domain Commands

**Search single domain:**
```bash
python main.py domain search myawesomeapp.com
```

**Search multiple domains:**
```bash
python main.py domain search "app.com,app.net,app.io" --multiple
````

**Get domain suggestions:**
```bash
python main.py domain suggest "coffee shop" --limit 10
```

**List owned domains:**
```bash
python main.py domain list
```

**Get domain details:**
```bash
python main.py domain info myexistingdomain.com
```

## Full Command Reference

### Deploy Command

```bash
python main.py deploy [OPTIONS]
```

**Required:**
- `--app-dir PATH` - Path to Next.js application

**Local Deployment:**
- `--output PATH` - Output directory (default: ./output_files/deployment)
- `--build-cmd CMD` - Build command (default: pnpm build)
- `--no-clean` - Don't clean destination before deployment
- `--timestamp` - Add timestamp to deployment folder

**S3 Deployment:**
- `--s3` - Deploy to AWS S3
- `--s3-bucket NAME` - S3 bucket name (required with --s3)
- `--s3-prefix PATH` - S3 prefix/folder path
- `--public` - Make S3 files publicly accessible

### Domain Commands

**Search:**
```bash
python main.py domain search DOMAIN [--multiple]
```

**Suggest:**
```bash
python main.py domain suggest QUERY [--limit N]
```

**List:**
```bash
python main.py domain list
```

**Info:**
```bash
python main.py domain info DOMAIN
```

## Configuration

Make sure you have configured `.env` file with your GoDaddy credentials:

```env
# GoDaddy API Configuration
GODADDY_API_KEY=your_api_key
GODADDY_API_SECRET=your_api_secret
GODADDY_ENV=OTE  # or PRODUCTION

# AWS Configuration (optional, for S3 deployment)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
```

## Examples

### Complete Workflow

```bash
# 1. Search for available domain
python main.py domain search mynewapp.com

# 2. Get suggestions if taken
python main.py domain suggest "new app" --limit 10

# 3. Build and deploy your app
python main.py deploy --app-dir ./my-nextjs-app --output ./deployment

# 4. Deploy to S3
python main.py deploy --app-dir ./my-nextjs-app --s3 --s3-bucket my-bucket --public

# 5. List your owned domains
python main.py domain list
```

## Help

For help on any command:
```bash
python main.py --help
python main.py deploy --help
python main.py domain --help
python main.py domain search --help
```
