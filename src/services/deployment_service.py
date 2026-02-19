"""
Deployment Service
Handles Next.js build and deployment operations (local and S3)
Refactored from script.py with enhanced architecture
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

from src.utils.logger import get_logger
from src.utils.config import get_settings

logger = get_logger(__name__)


class DeploymentError(Exception):
    """Base exception for deployment errors"""
    pass


class BuildError(DeploymentError):
    """Raised when build fails"""
    pass


class DeploymentService:
    """
    Service for building and deploying Next.js applications.
    Supports local deployment and AWS S3 upload.
    """
    
    def __init__(self, app_directory: Path):
        """
        Initialize deployment service.
        
        Args:
            app_directory: Path to Next.js application directory
            
        Raises:
            FileNotFoundError: If app_directory doesn't exist
        """
        self.app_directory = Path(app_directory).resolve()
        
        if not self.app_directory.exists():
            raise FileNotFoundError(f"Application directory not found: {self.app_directory}")
        
        if not self.app_directory.is_dir():
            raise ValueError(f"Path is not a directory: {self.app_directory}")
        
        logger.info(f"Deployment service initialized for: {self.app_directory}")
    
    def run_build(self, build_command: str = "pnpm build") -> None:
        """
        Run the build command for the Next.js application.
        
        Args:
            build_command: Build command to run (default: "pnpm build")
            
        Raises:
            BuildError: If build fails
        """
        logger.info(f"Running build command: {build_command}")
        logger.info(f"Working directory: {self.app_directory}")
        
        try:
            result = subprocess.run(
                build_command,
                cwd=self.app_directory,
                check=True,
                shell=True,  # Required for Windows
                capture_output=True,
                text=True,
            )
            
            logger.info("✅ Build completed successfully")
            logger.debug(f"Build output: {result.stdout}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Build failed with exit code {e.returncode}")
            logger.error(f"Error output: {e.stderr}")
            raise BuildError(f"Build failed: {e.stderr}") from e
    
    def get_build_directory(self) -> Path:
        """
        Detect and return the build output directory.
        
        For Next.js:
        - 'out' folder for static export (next build && next export)
        - '.next' folder for standard build
        
        Returns:
            Path to build output directory
            
        Raises:
            FileNotFoundError: If no build output found
        """
        possible_build_dirs = ["out", ".next", "dist", "build"]
        
        for folder in possible_build_dirs:
            candidate = self.app_directory / folder
            if candidate.exists() and candidate.is_dir():
                logger.info(f"Found build directory: {candidate}")
                return candidate
        
        raise FileNotFoundError(
            f"No build output folder found in {self.app_directory}. "
            f"Expected one of: {', '.join(possible_build_dirs)}"
        )
    
    def deploy_local(
        self,
        destination: Path,
        clean_destination: bool = True,
        add_timestamp: bool = False
    ) -> Path:
        """
        Deploy build output to local directory.
        
        Args:
            destination: Target directory for deployment
            clean_destination: Remove existing destination before copying
            add_timestamp: Add timestamp suffix to destination folder
            
        Returns:
            Path to deployment directory
            
        Raises:
            DeploymentError: If deployment fails
        """
        build_dir = self.get_build_directory()
        destination = Path(destination).resolve()
        
        # Add timestamp if requested
        if add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = destination.parent / f"{destination.name}_{timestamp}"
        
        logger.info(f"Deploying to local directory")
        logger.info(f"Source: {build_dir}")
        logger.info(f"Destination: {destination}")
        
        try:
            # Clean destination if it exists and clean is requested
            if destination.exists() and clean_destination:
                logger.warning(f"Removing existing destination: {destination}")
                shutil.rmtree(destination)
            
            # Copy build output
            logger.info("Copying build files...")
            shutil.copytree(build_dir, destination)
            
            logger.info(f"✅ Deployment successful: {destination}")
            return destination
            
        except Exception as e:
            logger.error(f"❌ Deployment failed: {str(e)}")
            raise DeploymentError(f"Local deployment failed: {str(e)}") from e
    
    def deploy_s3(
        self,
        bucket_name: str,
        s3_prefix: str = "",
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        make_public: bool = False
    ) -> Dict[str, Any]:
        """
        Deploy build output to AWS S3 bucket.
        
        Args:
            bucket_name: S3 bucket name
            s3_prefix: Prefix for S3 keys (folder path)
            aws_access_key: AWS access key (uses config if None)
            aws_secret_key: AWS secret key (uses config if None)
            aws_region: AWS region (uses config if None)
            make_public: Make uploaded files public
            
        Returns:
            Dictionary with deployment info (bucket, prefix, file count)
            
        Raises:
            DeploymentError: If S3 deployment fails
            ImportError: If boto3 not installed
        """
        if not S3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3 deployment. "
                "Install it with: pip install boto3"
            )
        
        build_dir = self.get_build_directory()
        
        # Get AWS credentials from config if not provided
        if not all([aws_access_key, aws_secret_key]):
            config = get_settings()
            aws_access_key = aws_access_key or config.aws_access_key_id
            aws_secret_key = aws_secret_key or config.aws_secret_access_key
            aws_region = aws_region or config.aws_region
        
        logger.info(f"Deploying to S3 bucket: {bucket_name}")
        logger.info(f"S3 prefix: {s3_prefix or '(root)'}")
        logger.info(f"Region: {aws_region}")
        
        try:
            # Initialize S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Upload files
            uploaded_files = []
            
            for root, dirs, files in os.walk(build_dir):
                for file in files:
                    local_path = Path(root) / file
                    relative_path = local_path.relative_to(build_dir)
                    
                    # Construct S3 key
                    s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/").lstrip("/")
                    
                    # Determine content type
                    content_type = self._get_content_type(file)
                    
                    # Upload file
                    extra_args = {'ContentType': content_type}
                    if make_public:
                        extra_args['ACL'] = 'public-read'
                    
                    logger.debug(f"Uploading: {s3_key}")
                    s3_client.upload_file(
                        str(local_path),
                        bucket_name,
                        s3_key,
                        ExtraArgs=extra_args
                    )
                    
                    uploaded_files.append(s3_key)
            
            logger.info(f"✅ S3 deployment successful: {len(uploaded_files)} files uploaded")
            
            return {
                "bucket": bucket_name,
                "prefix": s3_prefix,
                "region": aws_region,
                "file_count": len(uploaded_files),
                "files": uploaded_files[:10]  # First 10 files
            }
            
        except ClientError as e:
            logger.error(f"❌ S3 deployment failed: {str(e)}")
            raise DeploymentError(f"S3 deployment failed: {str(e)}") from e
        
        except Exception as e:
            logger.error(f"❌ Deployment failed: {str(e)}")
            raise DeploymentError(f"S3 deployment failed: {str(e)}") from e
    
    def build_and_deploy_local(
        self,
        destination: Path,
        build_command: str = "pnpm build",
        clean_destination: bool = True,
        add_timestamp: bool = False
    ) -> Path:
        """
        Complete workflow: Build and deploy to local directory.
        
        Args:
            destination: Target directory
            build_command: Build command
            clean_destination: Remove existing destination
            add_timestamp: Add timestamp to folder name
            
        Returns:
            Path to deployment directory
        """
        logger.info("=" * 60)
        logger.info("Starting Build & Deploy Workflow (Local)")
        logger.info("=" * 60)
        
        # Step 1: Build
        self.run_build(build_command)
        
        # Step 2: Deploy
        result = self.deploy_local(
            destination=destination,
            clean_destination=clean_destination,
            add_timestamp=add_timestamp
        )
        
        logger.info("=" * 60)
        logger.info("✅ Workflow Complete")
        logger.info("=" * 60)
        
        return result
    
    def build_and_deploy_s3(
        self,
        bucket_name: str,
        s3_prefix: str = "",
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        build_command: str = "pnpm build",
        make_public: bool = False
    ) -> Dict[str, Any]:
        """
        Complete workflow: Build and deploy to S3.
        
        Args:
            bucket_name: S3 bucket name
            s3_prefix: S3 prefix (folder)
            build_command: Build command
            make_public: Make files public
            
        Returns:
            Deployment info dictionary
        """
        logger.info("=" * 60)
        logger.info("Starting Build & Deploy Workflow (S3)")
        logger.info("=" * 60)
        
        # Step 1: Build
        self.run_build(build_command)
        
        # Step 2: Deploy to S3
        result = self.deploy_s3(
            bucket_name=bucket_name,
            s3_prefix=s3_prefix,
            make_public=make_public,
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            aws_region=aws_region
        )
        
        logger.info("=" * 60)
        logger.info("✅ Workflow Complete")
        logger.info("=" * 60)
        
        return result
    
    @staticmethod
    def _get_content_type(filename: str) -> str:
        """
        Determine content type based on file extension.
        
        Args:
            filename: File name
            
        Returns:
            Content type string
        """
        extension = Path(filename).suffix.lower()
        
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            '.ttf': 'font/ttf',
            '.eot': 'application/vnd.ms-fontobject',
            '.xml': 'application/xml',
            '.txt': 'text/plain',
        }
        
        return content_types.get(extension, 'application/octet-stream')
