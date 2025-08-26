"""
S3 Utilities for improved URL generation and public access configuration.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_public_s3_url(s3_key: str, use_cloudfront: bool = True) -> str:
    """
    Generate a public S3 URL, optionally using CloudFront for better performance.
    
    Args:
        s3_key: The S3 object key (path within bucket)
        use_cloudfront: Whether to use CloudFront if available
        
    Returns:
        Public URL for the S3 object
    """
    # Check if CloudFront is configured and should be used
    cloudfront_domain = os.getenv("CLOUDFRONT_DOMAIN")
    if use_cloudfront and cloudfront_domain:
        return f"https://{cloudfront_domain}/{s3_key}"
    
    # Fallback to direct S3 URL
    bucket_name = os.getenv("S3_BUCKET_NAME")
    region = os.getenv("AWS_REGION")
    
    if not bucket_name or not region:
        logger.error("S3_BUCKET_NAME or AWS_REGION not configured")
        raise ValueError("S3 configuration incomplete")
    
    return f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"


def get_s3_bucket_policy_json(bucket_name: str) -> str:
    """
    Generate the JSON bucket policy for public read access.
    
    Args:
        bucket_name: Name of the S3 bucket
        
    Returns:
        JSON string of the bucket policy
    """
    return f'''{{
  "Version": "2012-10-17",
  "Statement": [
    {{
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::{bucket_name}/*"
    }}
  ]
}}'''


def get_cors_configuration() -> list:
    """
    Get the CORS configuration for S3 bucket to allow web browser access.
    
    Returns:
        List containing CORS configuration
    """
    return [
        {
            "AllowedHeaders": ["Authorization", "Content-Length", "Content-Type"],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3000
        }
    ]


def validate_s3_url(url: str) -> bool:
    """
    Validate if a URL looks like a proper S3 URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL appears to be a valid S3 URL
    """
    if not url:
        return False
    
    # Check for S3 domain patterns
    s3_patterns = [
        ".s3.amazonaws.com",
        ".s3-",
        ".s3.",
        "//s3.amazonaws.com"
    ]
    
    return any(pattern in url for pattern in s3_patterns)


def extract_s3_key_from_url(s3_url: str) -> Optional[str]:
    """
    Extract the S3 key (object path) from an S3 URL.
    
    Args:
        s3_url: Full S3 URL
        
    Returns:
        S3 key if extractable, None otherwise
    """
    try:
        # Handle different S3 URL formats
        if ".s3.amazonaws.com/" in s3_url:
            return s3_url.split(".s3.amazonaws.com/")[1]
        elif ".s3-" in s3_url and "/" in s3_url:
            # Handle region-specific URLs like bucket.s3-us-west-2.amazonaws.com/key
            return s3_url.split("/", 3)[-1] if s3_url.count("/") >= 3 else None
        elif ".s3." in s3_url and "/" in s3_url:
            # Handle URLs like bucket.s3.region.amazonaws.com/key
            return s3_url.split("/", 3)[-1] if s3_url.count("/") >= 3 else None
        
        return None
    except Exception as e:
        logger.warning(f"Could not extract S3 key from URL {s3_url}: {e}")
        return None


# Configuration constants for AWS CLI or Terraform
AWS_CLI_COMMANDS = """
# AWS CLI commands to configure S3 bucket for public access

# 1. Remove public access block
aws s3api delete-public-access-block --bucket YOUR_BUCKET_NAME

# 2. Apply bucket policy for public read access
aws s3api put-bucket-policy --bucket YOUR_BUCKET_NAME --policy file://bucket-policy.json

# 3. Set CORS configuration
aws s3api put-bucket-cors --bucket YOUR_BUCKET_NAME --cors-configuration file://cors-config.json
"""

TERRAFORM_CONFIG = """
# Terraform configuration for S3 bucket public access

resource "aws_s3_bucket_public_access_block" "example" {
  bucket = aws_s3_bucket.example.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "example" {
  bucket = aws_s3_bucket.example.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.example.arn}/*"
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.example]
}

resource "aws_s3_bucket_cors_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  cors_rule {
    allowed_headers = ["Authorization", "Content-Length", "Content-Type"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}
"""
