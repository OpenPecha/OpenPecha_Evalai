import os
import logging
import aioboto3
from typing import Any, Tuple
from uuid import UUID
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

# Set up logging
logger = logging.getLogger(__name__)


def sanitize_title_for_s3(title: str) -> str:
    """
    Sanitize challenge title for use in S3 key paths.
    
    Args:
        title: Original challenge title
        
    Returns:
        Sanitized title safe for S3 keys
    """
    import re
    
    # Convert to lowercase and replace spaces with underscores
    sanitized = title.lower().replace(' ', '_')
    
    # Remove special characters, keep only alphanumeric, underscores, and hyphens
    sanitized = re.sub(r'[^a-z0-9_-]', '', sanitized)
    
    # Limit length to 50 characters
    sanitized = sanitized[:50]
    
    # Remove trailing underscores or hyphens
    sanitized = sanitized.rstrip('_-')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "untitled_challenge"
    
    return sanitized


async def ground_truth_upload_s3(file: Any, filename: str, challenge_id: UUID, challenge_title: str = None) -> Tuple[bool, str, str]:
    """
    Upload ground truth JSON file to S3 for a specific challenge.
    
    Args:
        file: File object to upload
        filename: Name of the file
        challenge_id: UUID of the challenge
        
    Returns:
        Tuple of (success, message, s3_url)
    """
    session = aioboto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )
    
    # Dedicated folder structure for ground truth files
    # Use challenge title if provided, otherwise fall back to challenge ID
    if challenge_title:
        sanitized_title = sanitize_title_for_s3(challenge_title)
        folder_name = f"evalai/ground_truth/{sanitized_title}_{challenge_id}"
    else:
        folder_name = f"evalai/ground_truth/{challenge_id}"

    async with session.client('s3') as s3_client:
        try:
            # Upload file to S3 with challenge-specific path
            s3_key = f"{folder_name}/{filename}"
            
            # Set proper Content-Type for JSON files
            extra_args = {
                'ContentType': 'application/json',
                'ContentDisposition': 'inline'
            }
            
            await s3_client.upload_fileobj(
                file,
                os.getenv("S3_BUCKET_NAME"),
                s3_key,
                ExtraArgs=extra_args
            )
            
            # Construct the S3 URL
            file_url = f"https://{os.getenv('S3_BUCKET_NAME')}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_key}"
            
            logger.info(f"Ground truth uploaded successfully: {file_url}")
            return True, "Ground truth uploaded successfully", file_url
            
        except NoCredentialsError:
            logger.error("AWS credentials not found for ground truth upload")
            return False, "AWS credentials not found", ""
        except PartialCredentialsError:
            logger.error("Incomplete AWS credentials for ground truth upload")
            return False, "Incomplete AWS credentials", ""
        except Exception as e:
            logger.error(f"Failed to upload ground truth: {str(e)}")
            return False, f"Failed to upload ground truth: {str(e)}", ""


def validate_ground_truth_structure(json_data: list) -> Tuple[bool, str]:
    """
    Validate the structure of ground truth JSON data.
    
    Args:
        json_data: List of dictionaries containing ground truth data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not isinstance(json_data, list):
            return False, "Ground truth JSON must be an array of objects"
        
        if len(json_data) == 0:
            return False, "Ground truth JSON cannot be empty"
        
        # Validate each record has required fields
        for i, record in enumerate(json_data):
            if not isinstance(record, dict):
                return False, f"Record {i+1} must be an object"
            
            if 'filename' not in record:
                return False, f"Record {i+1} missing required 'filename' field"
            
            if 'label' not in record:
                return False, f"Record {i+1} missing required 'label' field"
            
            if not isinstance(record['filename'], str) or not record['filename'].strip():
                return False, f"Record {i+1} 'filename' must be a non-empty string"
            
            if not isinstance(record['label'], str):
                return False, f"Record {i+1} 'label' must be a string"
        
        # Check for duplicate filenames
        filenames = [record['filename'] for record in json_data]
        if len(filenames) != len(set(filenames)):
            return False, "Ground truth contains duplicate filenames"
        
        logger.info(f"Ground truth validation passed: {len(json_data)} records")
        return True, f"Ground truth validation passed: {len(json_data)} records"
        
    except Exception as e:
        logger.error(f"Error validating ground truth structure: {str(e)}")
        return False, f"Validation error: {str(e)}"


async def process_ground_truth_file(file: Any, challenge_id: UUID, challenge_title: str = None) -> Tuple[bool, str, str]:
    """
    Complete processing of ground truth file including validation and S3 upload.
    
    Args:
        file: UploadFile object from FastAPI
        challenge_id: UUID of the challenge
        
    Returns:
        Tuple of (success, message, s3_url)
    """
    try:
        # Validate file exists and has filename
        if not file or not file.filename:
            return False, "No file provided or filename missing", ""
        
        # Validate file type
        if not file.filename.lower().endswith('.json'):
            return False, "Ground truth file must be a JSON file (.json extension required)", ""
        
        # Read and validate file size
        content = await file.read()
        file_size = len(content)
        
        if file_size > 50 * 1024 * 1024:  # 50MB in bytes
            return False, "Ground truth file size exceeds 50MB limit", ""
        
        if file_size == 0:
            return False, "Ground truth file is empty", ""
        
        # Parse JSON content
        try:
            import json
            json_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format in ground truth file: {str(e)}", ""
        except UnicodeDecodeError as e:
            return False, f"File encoding error in ground truth file: {str(e)}", ""
        
        # Validate ground truth structure
        is_valid, validation_message = validate_ground_truth_structure(json_data)
        if not is_valid:
            return False, f"Ground truth validation failed: {validation_message}", ""
        
        # Upload to S3
        from io import BytesIO
        import uuid as uuid_module
        
        file_obj = BytesIO(content)
        
        # Preserve original filename with timestamp and unique ID suffix
        from datetime import datetime
        
        original_name = file.filename
        name_without_ext = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
        timestamp = datetime.now().strftime("%Y-%m-%d")
        unique_filename = f"{name_without_ext}_{timestamp}_{uuid_module.uuid4().hex[:8]}.json"
        
        upload_success, upload_result, s3_url = await ground_truth_upload_s3(
            file=file_obj,
            filename=unique_filename,
            challenge_id=challenge_id,
            challenge_title=challenge_title
        )
        
        if not upload_success:
            return False, f"Failed to upload ground truth to S3: {upload_result}", ""
        
        logger.info(f"Ground truth processed successfully: {s3_url}")
        return True, f"Ground truth uploaded successfully ({len(json_data)} records)", s3_url
        
    except Exception as e:
        logger.error(f"Unexpected error processing ground truth file: {str(e)}")
        return False, f"Unexpected error processing ground truth file: {str(e)}", ""
