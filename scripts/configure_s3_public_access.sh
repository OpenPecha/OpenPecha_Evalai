#!/bin/bash

# Script to configure S3 bucket for public read access
# Usage: ./configure_s3_public_access.sh YOUR_BUCKET_NAME

set -e

BUCKET_NAME="$1"

if [ -z "$BUCKET_NAME" ]; then
    echo "Usage: $0 BUCKET_NAME"
    echo "Example: $0 my-evalai-bucket"
    exit 1
fi

echo "🔧 Configuring S3 bucket '$BUCKET_NAME' for public read access..."

# Check if bucket exists
if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo "❌ Bucket '$BUCKET_NAME' does not exist or you don't have access to it"
    exit 1
fi

echo "✅ Bucket exists and accessible"

# Step 1: Remove public access block
echo "📝 Removing public access block..."
aws s3api delete-public-access-block --bucket "$BUCKET_NAME" || {
    echo "⚠️  Could not remove public access block (it might not exist)"
}

# Step 2: Create bucket policy JSON
POLICY_FILE="/tmp/bucket-policy-${BUCKET_NAME}.json"
cat > "$POLICY_FILE" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    }
  ]
}
EOF

echo "📝 Applying bucket policy for public read access..."
aws s3api put-bucket-policy --bucket "$BUCKET_NAME" --policy "file://$POLICY_FILE"

# Step 3: Create CORS configuration
CORS_FILE="/tmp/cors-config-${BUCKET_NAME}.json"
cat > "$CORS_FILE" << EOF
{
  "CORSRules": [
    {
      "AllowedHeaders": ["Authorization", "Content-Length", "Content-Type"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

echo "📝 Configuring CORS..."
aws s3api put-bucket-cors --bucket "$BUCKET_NAME" --cors-configuration "file://$CORS_FILE"

# Clean up temporary files
rm -f "$POLICY_FILE" "$CORS_FILE"

echo "✅ S3 bucket '$BUCKET_NAME' configured for public read access!"
echo ""
echo "🧪 Test your configuration:"
echo "1. Upload a test file: aws s3 cp test.txt s3://$BUCKET_NAME/test.txt"
echo "2. Access it directly: https://$BUCKET_NAME.s3.amazonaws.com/test.txt"
echo ""
echo "⚠️  Security Note: All objects in this bucket are now publicly readable!"
echo "   Make sure you don't store sensitive data in this bucket."
