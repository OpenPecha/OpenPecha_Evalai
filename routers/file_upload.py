from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from CRUD.upload_file_to_s3 import simple_upload_to_s3
import uuid

router = APIRouter(prefix="/file-upload", tags=["file-upload"])

@router.post("")
async def upload_file(file: UploadFile = File(...)):
    """
    Simple file upload to S3 without validation.
    This endpoint is for testing and general file uploads - no content validation is performed.
    """
    try:
        # Generate a unique filename to avoid conflicts
        file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
        unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())

        # Upload file to S3 without any validation
        success, message, file_url = await simple_upload_to_s3(
            file=file.file,
            filename=unique_filename,
            folder_path="evalai/test_uploads"  # Separate folder for test uploads
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Upload failed: {message}")

        return JSONResponse(
            content={
                "message": "File uploaded successfully (no validation performed)",
                "file_url": file_url,
                "original_filename": file.filename,
                "uploaded_filename": unique_filename,
                "validation": "none"
            }, 
            status_code=200
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")