"""
Quick test to verify Phase 1 setup is working correctly
Run this to test: python -m pytest tests/test_phase1_setup.py -v
"""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_folder_structure_exists():
    """Test that all required folders exist"""
    base_path = Path(__file__).parent.parent
    
    required_dirs = [
        "src",
        "src/api",
        "src/services",
        "src/utils",
        "src/cli",
        "tests",
        "logs"
    ]
    
    for dir_path in required_dirs:
        full_path = base_path / dir_path
        assert full_path.exists(), f"Directory {dir_path} should exist"
        assert full_path.is_dir(), f"{dir_path} should be a directory"


def test_required_files_exist():
    """Test that all required configuration files exist"""
    base_path = Path(__file__).parent.parent
    
    required_files = [
        ".env",
        ".env.example",
        ".gitignore",
        "requirements.txt",
        "src/__init__.py",
        "src/utils/__init__.py",
        "src/utils/config.py",
        "src/utils/logger.py",
        "src/utils/validators.py"
    ]
    
    for file_path in required_files:
        full_path = base_path / file_path
        assert full_path.exists(), f"File {file_path} should exist"
        assert full_path.is_file(), f"{file_path} should be a file"


def test_gitignore_has_env():
    """Test that .gitignore includes .env to prevent credential leaks"""
    base_path = Path(__file__).parent.parent
    gitignore_path = base_path / ".gitignore"
    
    content = gitignore_path.read_text()
    assert ".env" in content, ".gitignore should include .env"
    assert "logs/" in content, ".gitignore should include logs/"


def test_validators_import():
    """Test that validators module can be imported"""
    from src.utils.validators import validate_domain, validate_email, ValidationError
    
    # Test valid domain
    assert validate_domain("example.com") == "example.com"
    assert validate_domain("EXAMPLE.COM") == "example.com"  # Should lowercase
    
    # Test invalid domain
    with pytest.raises(ValidationError):
        validate_domain("invalid domain with spaces")
    
    # Test valid email
    assert validate_email("test@example.com") == "test@example.com"
    
    # Test invalid email
    with pytest.raises(ValidationError):
        validate_email("invalid-email")


def test_logger_import():
    """Test that logger module can be imported and used"""
    from src.utils.logger import get_logger
    
    logger = get_logger("test", level="INFO")
    assert logger is not None
    assert logger.name == "test"


@pytest.mark.skipif(
    not Path(".env").exists() or "your_" in Path(".env").read_text(),
    reason="Skipping config test - .env not configured with real credentials yet"
)
def test_config_loads():
    """Test that config loads from .env (skipped if not configured)"""
    from src.utils.config import get_settings
    
    settings = get_settings()
    assert settings.godaddy_env in ["OTE", "PRODUCTION"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
