import json
from typing import Dict, Any, Tuple, List, Set
from dotenv import load_dotenv
import logging
import aioboto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import os
from uuid import UUID
import requests

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
    Validate that the JSON contains required columns: 'Filename' and 'Inference'
    
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

async def validate_submission_filenames(submission_data: List[Dict], challenge_ground_truth_url: str) -> Tuple[bool, str, Set[str]]:
    """
    Validate that submission filenames match the challenge ground truth filenames.
    
    Args:
        submission_data: List of submission records with 'filename' and 'prediction'
        challenge_ground_truth_url: S3 URL of the challenge ground truth JSON
        
    Returns:
        Tuple of (is_valid, error_message, valid_filenames_set)
    """
    try:
        # Download challenge ground truth directly via HTTP
        try:
            # Disable SSL verification for S3 URLs to avoid certificate issues with custom bucket names
            verify_ssl = False if 'amazonaws.com' in challenge_ground_truth_url else True
            response = requests.get(challenge_ground_truth_url, timeout=30, verify=verify_ssl)
            response.raise_for_status()  # Raises exception for bad status codes
            ground_truth_data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download challenge ground truth: {str(e)}")
            return False, f"Failed to access challenge ground truth: {str(e)}", set()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse challenge ground truth JSON: {str(e)}")
            return False, f"Challenge ground truth is not valid JSON: {str(e)}", set()
        
        # Extract filenames from ground truth (using 'filename' field)
        if not isinstance(ground_truth_data, list):
            return False, "Challenge ground truth must be a list of records", set()
        
        ground_truth_filenames = set()
        for record in ground_truth_data:
            if 'filename' not in record:
                return False, "Challenge ground truth records missing 'filename' field", set()
            ground_truth_filenames.add(record['filename'])
        
        # Extract filenames from submission
        submission_filenames = set()
        for record in submission_data:
            submission_filenames.add(record['filename'])
        
        # Check if submission filenames are a subset of ground truth filenames
        invalid_filenames = submission_filenames - ground_truth_filenames
        
        if invalid_filenames:
            invalid_list = list(invalid_filenames)[:5]  # Show first 5 invalid filenames
            error_msg = f"Submission contains {len(invalid_filenames)} filename(s) not found in challenge ground truth. Examples: {invalid_list}"
            if len(invalid_filenames) > 5:
                error_msg += f" (and {len(invalid_filenames) - 5} more)"
            return False, error_msg, ground_truth_filenames
        
        # Check if submission has any valid filenames
        if not submission_filenames:
            return False, "Submission contains no filenames", ground_truth_filenames
        
        valid_count = len(submission_filenames)
        total_ground_truth = len(ground_truth_filenames)
        
        logger.info(f"Filename validation successful: {valid_count}/{total_ground_truth} files in submission")
        return True, f"All {valid_count} submission filenames are valid (out of {total_ground_truth} total challenge files)", ground_truth_filenames
        
    except Exception as e:
        logger.error(f"Error during filename validation: {str(e)}")
        return False, f"Filename validation error: {str(e)}", set()

async def upload_file_to_s3(file: Any, filename: str, user_id: UUID, model_id: UUID, submission_id: UUID, challenge_name: str) -> Tuple[bool, str, str]:
    session = aioboto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")
    )
    
    folder_name = f"evalai/challenges/{challenge_name}"

    async with session.client('s3') as s3_client:
        try:
            # Upload file to S3
            # Use submission ID-based versioning to prevent overwrites
            s3_key = f"{folder_name}/{submission_id}_{filename}"
            
            # Set proper Content-Type for JSON files to display in browser
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
            # Construct the S3 URL - use utility function for better URL generation
            from .s3_utils import generate_public_s3_url
            try:
                file_url = generate_public_s3_url(s3_key)
            except ValueError:
                # Fallback to direct URL construction if utils fail
                file_url = f"https://{os.getenv('S3_BUCKET_NAME')}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_key}"
            
            return True, "Successful", file_url
        except NoCredentialsError:
            return False, "AWS credentials not found", ""
        except PartialCredentialsError:
            return False, "Incomplete AWS credentials", ""
        except Exception as e:
            return False, f"Failed to upload file: {str(e)}", ""

async def process_json_file_upload(file_content: bytes, filename: str, user_id: UUID, model_id: UUID, submission_id: UUID, challenge_name: str, challenge_ground_truth_url: str = None) -> Tuple[bool, str, str, Dict[Any, Any]]:
    """
    Complete process for validating and uploading JSON file
    
    Args:
        file_content: The file content as bytes
        filename: Original filename
        user_id: ID of the user uploading the file
        model_id: ID of the model for organization
        submission_id: ID of the submission for versioning
        challenge_name: Name of the challenge for S3 path organization
        
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
        
        # Validate filenames against challenge ground truth (if provided)
        if challenge_ground_truth_url:
            filename_valid, filename_message, valid_filenames = await validate_submission_filenames(json_data, challenge_ground_truth_url)
            
            if not filename_valid:
                logger.warning(f"Filename validation failed for file {filename}: {filename_message}")
                return False, filename_message, "", {}
            
            logger.info(f"Filename validation passed: {filename_message}")
        
        # Upload to S3 if validation passes
        # Convert file_content back to file-like object for S3 upload
        from io import BytesIO
        file_obj = BytesIO(file_content)
        upload_success, upload_result, file_url = await upload_file_to_s3(file_obj, filename, user_id, model_id, submission_id, challenge_name)
        
        if upload_success:
            logger.info(f"File {filename} processed successfully")
            return True, "File uploaded successfully", file_url, json_data
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