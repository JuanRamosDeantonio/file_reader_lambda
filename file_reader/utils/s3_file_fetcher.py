# file_reader/utils/s3_file_fetcher.py

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import tempfile
import logging
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger(__name__)

class S3FileFetcher:
    """
    Downloads files from S3 paths and saves them temporarily to disk.
    Enhanced with robust error handling and logging.
    """

    def __init__(self, region_name: Optional[str] = None):
        """
        Initialize S3 client with optional region specification.
        
        Args:
            region_name: AWS region name. If None, uses default region.
        """
        try:
            self.s3 = boto3.client("s3", region_name=region_name)
            logger.info("✅ S3 client initialized successfully")
        except NoCredentialsError:
            logger.error("❌ AWS credentials not configured")
            raise ValueError(
                "AWS credentials not configured. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
                "or configure AWS CLI with 'aws configure'"
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {e}")
            raise

    def download_to_temp(self, s3_uri: str) -> str:
        """
        Downloads a file from S3 and saves it to a temporary file.
        Enhanced with comprehensive error handling and validation.

        Args:
            s3_uri (str): Full path in format s3://bucket/key

        Returns:
            str: Local temporary path of downloaded file
            
        Raises:
            ValueError: For various S3-related errors
        """
        # Validate S3 URI format
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI format. Expected 's3://bucket/key', got: {s3_uri}")
        
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        if not bucket:
            raise ValueError(f"No bucket specified in S3 URI: {s3_uri}")
        
        if not key:
            raise ValueError(f"No key specified in S3 URI: {s3_uri}")

        # Get object info first (validates existence and gets metadata)
        try:
            obj_info = self._get_object_info(bucket, key)
            logger.info(f"📊 S3 object: {obj_info['size']:,} bytes, {obj_info['content_type']}")
        except Exception as e:
            logger.error(f"❌ Failed to get S3 object info: {e}")
            raise

        # Determine filename for temp file
        filename = key.split('/')[-1] if key else "s3_download"

        try:
            with tempfile.NamedTemporaryFile(delete=False, 
                                           suffix=f"_{filename}",
                                           prefix="s3_") as tmp:
                
                logger.info(f"📥 Downloading from S3: s3://{bucket}/{key}")
                self.s3.download_fileobj(bucket, key, tmp)
                temp_path = tmp.name
                
            logger.info(f"✅ Successfully downloaded to: {temp_path}")
            return temp_path
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = self._get_friendly_error_message(error_code, bucket, key)
            logger.error(f"❌ S3 download failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"❌ Unexpected error during S3 download: {e}")
            raise ValueError(f"Failed to download from S3: {e}")

    def check_object_exists(self, s3_uri: str) -> bool:
        """
        Check if S3 object exists without downloading it.
        
        Args:
            s3_uri: S3 URI in format s3://bucket/key
            
        Returns:
            True if object exists, False otherwise
        """
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        
        try:
            self.s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def _get_object_info(self, bucket: str, key: str) -> dict:
        """Get S3 object metadata without downloading."""
        try:
            response = self.s3.head_object(Bucket=bucket, Key=key)
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'content_type': response.get('ContentType', 'unknown'),
                'etag': response.get('ETag', '').strip('"')
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise ValueError(f"S3 object not found: s3://{bucket}/{key}")
            elif error_code == 'NoSuchBucket':
                raise ValueError(f"S3 bucket not found: {bucket}")
            else:
                raise ValueError(f"S3 error getting object info: {e}")

    def _get_friendly_error_message(self, error_code: str, bucket: str, key: str) -> str:
        """Convert AWS error codes to user-friendly messages."""
        error_messages = {
            'NoSuchBucket': f"S3 bucket '{bucket}' does not exist or you don't have access",
            'NoSuchKey': f"File '{key}' not found in bucket '{bucket}'",
            'AccessDenied': f"Access denied to s3://{bucket}/{key}. Check your permissions",
            'InvalidBucketName': f"Invalid bucket name: '{bucket}'",
            'PermanentRedirect': f"Bucket '{bucket}' is in a different region",
            'SlowDown': "S3 is throttling requests. Please retry later",
        }
        
        return error_messages.get(
            error_code, 
            f"S3 error ({error_code}) accessing s3://{bucket}/{key}"
        )

    @staticmethod
    def is_s3_path(path: str) -> bool:
        """
        Check if a path is an S3 path.
        
        Args:
            path: Path to check
            
        Returns:
            True if path starts with s3://, False otherwise
        """
        return path.lower().startswith("s3://")


# Convenience functions for backward compatibility and simple usage
def download_from_s3(s3_uri: str) -> str:
    """
    Simple function to download from S3 (backward compatibility).
    
    Args:
        s3_uri: S3 URI in format s3://bucket/key
        
    Returns:
        Path to temporary file
    """
    fetcher = S3FileFetcher()
    return fetcher.download_to_temp(s3_uri)


def is_s3_path(path: str) -> bool:
    """
    Check if a path is an S3 path (convenience function).
    
    Args:
        path: Path to check
        
    Returns:
        True if path starts with s3://, False otherwise
    """
    return S3FileFetcher.is_s3_path(path)