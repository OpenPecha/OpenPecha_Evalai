import boto3
import json
import uuid
import os
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
from botocore.exceptions import ClientError, NoCredentialsError
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

def validate_json_structure(json_data: Dict[Any, Any]) -> Tuple[bool, str]:
    """
    Validate that the JSON contains required columns: 'filename' and 'prediction'
    
    Args:
        json_data: The parsed JSON data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check if it's a list of records or a single record
        if isinstance(json_data, list):
            if not json_data:
                return False, "JSON file is empty"
            # Check the first record for required columns
            sample_record = json_data[0]
        elif isinstance(json_data, dict):
            sample_record = json_data
        else:
            return False, "JSON must be either a dictionary or a list of dictionaries"
        
        # Check for required columns
        required_columns = ['filename', 'prediction']
        missing_columns = []
        
        for column in required_columns:
            if column not in sample_record:
                missing_columns.append(column)
        
        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"
        
        # If it's a list, validate all records have the required columns
        if isinstance(json_data, list):
            for i, record in enumerate(json_data):
                for column in required_columns:
                    if column not in record:
                        return False, f"Record {i+1} is missing required column: {column}"
        
        return True, "Validation successful"
        
    except Exception as e:
        logger.error(f"Error during JSON validation: {str(e)}")
        return False, f"Validation error: {str(e)}"

def upload_file_to_s3(file_content: bytes, filename: str, content_type: str = "application/json") -> Tuple[bool, str, str]:
    """
    Upload file to S3 bucket
    
    Args:
        file_content: The file content as bytes
        filename: Original filename
        content_type: MIME type of the file
        
    Returns:
        Tuple of (success, s3_url_or_error_message, s3_key)
    """
    try:
        # Check if S3 credentials are configured
        if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME]):
            missing_vars = []
            if not AWS_ACCESS_KEY_ID:
                missing_vars.append("AWS_ACCESS_KEY_ID")
            if not AWS_SECRET_ACCESS_KEY:
                missing_vars.append("AWS_SECRET_ACCESS_KEY")
            if not S3_BUCKET_NAME:
                missing_vars.append("S3_BUCKET_NAME")
            
            error_msg = f"Missing AWS configuration: {', '.join(missing_vars)}"
            logger.error(error_msg)
            return False, error_msg, ""
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        
        # Generate unique filename
        file_extension = filename.split('.')[-1] if '.' in filename else 'json'
        unique_filename = f"submissions/{uuid.uuid4()}.{file_extension}"
        
        # Upload file to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=unique_filename,
            Body=file_content,
            ContentType=content_type,
            Metadata={
                'original_filename': filename,
                'upload_timestamp': str(uuid.uuid4())
            }
        )
        
        # Generate S3 URL
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{unique_filename}"
        
        logger.info(f"File uploaded successfully to S3: {s3_url}")
        return True, s3_url, unique_filename
        
    except NoCredentialsError:
        error_msg = "AWS credentials not found"
        logger.error(error_msg)
        return False, error_msg, ""
    except ClientError as e:
        error_msg = f"AWS S3 error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, ""
    except Exception as e:
        error_msg = f"Unexpected error during S3 upload: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, ""

def process_json_file_upload(file_content: bytes, filename: str) -> Tuple[bool, str, str, Dict[Any, Any]]:
    """
    Complete process for validating and uploading JSON file
    
    Args:
        file_content: The file content as bytes
        filename: Original filename
        
    Returns:
        Tuple of (success, message, s3_url, json_data)
    """
    try:
        # Parse JSON content
        json_str = file_content.decode('utf-8')
        json_data = json.loads(json_str)
        
        # Validate JSON structure
        is_valid, validation_message = validate_json_structure(json_data)
        
        if not is_valid:
            logger.warning(f"JSON validation failed for file {filename}: {validation_message}")
            return False, validation_message, "", {}
        
        # Upload to S3 if validation passes
        upload_success, upload_result, s3_key = upload_file_to_s3(file_content, filename)
        
        if upload_success:
            logger.info(f"File {filename} processed successfully")
            return True, "File uploaded successfully", upload_result, json_data
        else:
            logger.error(f"S3 upload failed for file {filename}: {upload_result}")
            return False, f"Upload failed: {upload_result}", "", {}
            
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format: {str(e)}"
        logger.error(f"JSON decode error for file {filename}: {error_msg}")
        return False, error_msg, "", {}
    except UnicodeDecodeError as e:
        error_msg = f"File encoding error: {str(e)}"
        logger.error(f"Encoding error for file {filename}: {error_msg}")
        return False, error_msg, "", {}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error processing file {filename}: {error_msg}")
        return False, error_msg, "", {}