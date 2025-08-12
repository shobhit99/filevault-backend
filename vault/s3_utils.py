import boto3
from botocore.config import Config
from django.conf import settings
from botocore.exceptions import NoCredentialsError, ClientError, BotoCoreError
import logging

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        # Validate AWS settings
        if not all([
            settings.AWS_ACCESS_KEY_ID,
            settings.AWS_SECRET_ACCESS_KEY,
            settings.AWS_STORAGE_BUCKET_NAME,
            settings.AWS_S3_REGION_NAME
        ]):
            logger.error("Missing AWS configuration. Please check your environment variables.")
            self.client = None
            self.bucket_name = None
            return
            
        try:
            self.client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
                config=Config(
                    signature_version='s3v4',
                    region_name=settings.AWS_S3_REGION_NAME,
                    s3={
                        'addressing_style': 'virtual'
                    }
                )
            )
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            
            # Test connection by checking if bucket exists
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"S3 bucket '{settings.AWS_STORAGE_BUCKET_NAME}' does not exist")
            elif error_code == '403':
                logger.error(f"Access denied to S3 bucket '{settings.AWS_STORAGE_BUCKET_NAME}'")
            else:
                logger.error(f"S3 ClientError: {e}")
            self.client = None
            self.bucket_name = None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.client = None
            self.bucket_name = None

    def upload_fileobj(self, file_obj, key):
        if not self.client:
            logger.error("S3 client not initialized")
            return False
            
        try:
            logger.info(f"Uploading file to S3: {key}")
            self.client.upload_fileobj(file_obj, self.bucket_name, key)
            logger.info(f"Successfully uploaded file to S3: {key}")
            return True
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return False
        except ClientError as e:
            logger.error(f"S3 upload failed for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading {key}: {e}")
            return False

    def generate_presigned_url(self, key, expiration=3600):
        if not self.client:
            logger.error("S3 client not initialized")
            return None
            
        try:
            logger.info(f"Generating presigned URL for: {key}")
            response = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for: {key}")
            return response
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return None
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL for {key}: {e}")
            return None

    def delete_object(self, key):
        if not self.client:
            logger.error("S3 client not initialized")
            return False
            
        try:
            logger.info(f"Deleting file from S3: {key}")
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted file from S3: {key}")
            return True
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            return False
        except ClientError as e:
            logger.error(f"S3 delete failed for {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting {key}: {e}")
            return False

    def check_connection(self):
        """Check if S3 connection is working"""
        if not self.client:
            return False, "S3 client not initialized"
            
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True, "S3 connection successful"
        except ClientError as e:
            return False, f"S3 connection failed: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"

s3_client = S3Client()
