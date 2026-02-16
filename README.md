# 🚀 GoDaddy Domain Management & Next.js Deployment System

A professional, enterprise-grade automation system for Next.js build/deployment and GoDaddy domain management.

## ✨ Features (Phase 1 Complete)

### Current Features
✅ **Next.js Build Automation** - Automated `pnpm build` execution  
✅ **Build Output Management** - Smart detection of `.next` or `out` folders  
✅ **Local Deployment** - Copy build files to local destination [For testing] 
✅ **S3 Upload Ready** - boto3 integration for AWS S3 deployment 
✅ **Configuration Management** - Environment-based config (OTE/PRODUCTION)  
✅ **Secure Credentials** - `.env` file with git-ignoring for API keys  
✅ **Colored Logging** - Beautiful console output with file logging  
✅ **Input Validation** - Domain, email, and phone validators  

### Coming Soon (Phase 2+)
🔄 **GoDaddy Domain Search** - Check domain availability  
🔄 **Domain Pricing** - Get real-time pricing from GoDaddy  
🔄 **Domain Purchase** - Automated domain registration  
🔄 **Interactive CLI** - Beautiful prompts and user experience  

---

## 📁 Project Structure

```
Temp-AI-Website/
├── .env                          # 🔒 Your GoDaddy API credentials (git-ignored)
├── .env.example                  # Template for credentials
├── .gitignore                    # Security: prevents credential leaks
├── requirements.txt              # Python dependencies
│
├── src/                          # Source code (enterprise structure)
│   ├── api/                      # External API integrations
│   │   └── (Phase 2: GoDaddy client)
│   │
│   ├── services/                 # Business logic layer
│   │   └── (Phase 3: Domain & deployment services)
│   │
│   ├── utils/                    # ✅ Utilities and helpers
│   │   ├── config.py            # ✅ Configuration loader (Pydantic)
│   │   ├── logger.py            # ✅ Colored logging system
│   │   └── validators.py        # ✅ Domain/email/phone validators
│   │
│   └── cli/                      # CLI interface
│       └── (Phase 4: Command implementations)
│
├── tests/                        # ✅ Test suite
│   ├── test_phase1_setup.py     # ✅ Phase 1 validation tests
│   └── (more tests in later phases)
│
├── logs/                         # Application logs (git-ignored)
├── main.py                       # Entry point
├── script.py                     # Legacy build script
├── build_files/                  # Next.js build artifacts
└── output_files/                 # Deployment outputs
```

---

## 🎯 Quick Start

### 1. **Install Dependencies**

```bash
# Using your virtual environment
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. **Configure GoDaddy API Credentials**

Edit the `.env` file and add your **GoDaddy OTE (test) credentials**:

```env
# .env file
GODADDY_API_KEY=your_actual_ote_api_key
GODADDY_API_SECRET=your_actual_ote_secret
GODADDY_ENV=OTE
LOG_LEVEL=INFO
```

> **⚠️ IMPORTANT**: Never commit the `.env` file to git! It's already in `.gitignore`.

### 3. **Verify Setup**

Run the Phase 1 validation tests:

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase1_setup.py -v
```

Expected output:
```
✅ 6 passed, 1 skipped (pending credentials configuration)
```

---

## 🔧 Current Usage (Phase 1)

### Build & Deploy Next.js App (Existing Feature)

```bash
python main.py --app-dir "C:\path\to\your\nextjs\app" --deploy-dir ".\output_files\deployment"
```

**What it does:**
1. Runs `pnpm build` in your Next.js app
2. Detects build output folder (`.next` or `out`)
3. Copies build files to deployment directory

---

## 🛠️ Development

### Run Tests

```bash
# All tests
.venv\Scripts\python.exe -m pytest tests/ -v

# Specific test file
.venv\Scripts\python.exe -m pytest tests/test_phase1_setup.py -v

# With coverage
.venv\Scripts\python.exe -m pytest tests/ --cov=src --cov-report=html
```

### Check Validators

```python
from src.utils.validators import validate_domain, validate_email

# Domain validation
domain = validate_domain("example.com")  # Returns: "example.com"
domain = validate_domain("EXAMPLE.COM")  # Returns: "example.com" (lowercased)

# Email validation
email = validate_email("test@example.com")  # Valid
```

### Check Configuration

```python
from src.utils.config import get_settings

settings = get_settings()
print(f"Environment: {settings.godaddy_env}")  # OTE or PRODUCTION
print(f"Base URL: {settings.godaddy_base_url}")
print(f"Is Production: {settings.is_production()}")
```

### Check Logging

```python
from src.utils.logger import get_logger

logger = get_logger("my_module")
logger.info("This is an info message")  # Green in console
logger.warning("This is a warning")     # Yellow in console
logger.error("This is an error")        # Red in console
```

---

## 📊 Environment Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GODADDY_API_KEY` | Your GoDaddy API key | - | ✅ Yes |
| `GODADDY_API_SECRET` | Your GoDaddy API secret | - | ✅ Yes |
| `GODADDY_ENV` | Environment (OTE or PRODUCTION) | `OTE` | ✅ Yes |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 | - | No |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 | - | No |
| `AWS_S3_BUCKET` | S3 bucket name | - | No |

---

## 🔐 Security Best Practices

✅ **`.env` is git-ignored** - Credentials never committed  
✅ **Separate OTE and PRODUCTION** - Test safely before going live  
✅ **Pydantic validation** - Credentials validated on load  
✅ **No hardcoded secrets** - All sensitive data in environment variables  

---

## 📝 Dependencies

### Core
- `boto3` - AWS S3 integration
- `requests` - HTTP client for API calls
- `python-dotenv` - Environment variable loading

### Configuration & Validation
- `pydantic` - Data validation
- `pydantic-settings` - Settings management

### CLI & User Experience
- `rich` - Beautiful terminal output
- `questionary` - Interactive prompts
- `click` - CLI framework

### Utilities
- `tenacity` - Retry logic with exponential backoff
- `colorlog` - Colored logging

### Testing
- `pytest` - Testing framework
- `pytest-mock` - Mocking support
- `pytest-cov` - Coverage reporting
- `responses` - Mock HTTP responses

---

## 🚦 Phase Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ **COMPLETE** | Architecture, config, logging, validators |
| **Phase 2** | 🔄 Next | GoDaddy API client integration |
| **Phase 3** | 📋 Planned | Business logic & services |
| **Phase 4** | 📋 Planned | Enhanced CLI with domain commands |
| **Phase 5** | 📋 Planned | Testing & validation |
| **Phase 6** | 📋 Planned | Documentation & deployment guides |

---

## 🎯 Next Steps

1. **Test the setup**: Run `pytest tests/test_phase1_setup.py -v`
2. **Configure credentials**: Add your GoDaddy OTE keys to `.env`
3. **Ready for Phase 2**: GoDaddy API client implementation

---

## 📚 Libraries Used

**For Local Testing:**
- `argparse` - CLI argument parsing
- `pathlib` - Path manipulation

**For Production:**
- `boto3` - AWS S3 uploads
- `requests` - GoDaddy API calls
- `pydantic` - Configuration & validation

**For Development:**
- `pytest` - Testing
- `rich` - Beautiful CLI output

---

## 🤝 Contributing

This project follows enterprise-grade architecture patterns:
- **Separation of concerns** - API, services, utils, CLI separated
- **Type safety** - Pydantic models for validation
- **Comprehensive logging** - All operations logged
- **Test coverage** - Unit and integration tests
- **Security first** - No hardcoded credentials

---

## 📄 License

Internal project for automation and learning.

---

**Built with ❤️ using Python, GoDaddy API, and modern DevOps practices.**