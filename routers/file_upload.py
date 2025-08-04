from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from CRUD.upload_file_to_s3 import upload_file_to_s3  # Assuming your existing file is named s3_upload.py
import uuid

router = APIRouter(prefix="/file-upload", tags=["file-upload"])

@router.post("")
async def upload_file(file: UploadFile = File(...)):
    """this is only for the testing whether we can upload json file into s3 or not."""
    try:
        # Generate a unique filename
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Upload file to S3
        file_url = await upload_file_to_s3(file.file, unique_filename, file.content_type)

        return JSONResponse(content={"message": "File uploaded successfully", "file_url": file_url}, status_code=200)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")