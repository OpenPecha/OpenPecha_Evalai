from fastapi import APIRouter, status, HTTPException, Depends, Path, Body, UploadFile, File, Form
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas.submission import SubmissionCreate, SubmissionRead
from CRUD.upload_file_to_s3 import process_json_file_upload
from CRUD.model import create_or_get_model
import uuid

router = APIRouter(prefix="/submissions", tags=["submissions"])

db_dependency = Annotated[Session, Depends(get_db)]

# ******** basic endpoints ********
@router.get("", response_model=List[SubmissionRead])
async def list_all_submissions(db: db_dependency):
    try:
        return db.query(models.Submission).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{submission_id}", response_model=SubmissionRead)
async def get_submission(db: db_dependency, submission_id: uuid.UUID = Path(..., description="This is the ID of the submission")):
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission

@router.post("/create", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def create_new_submission(db: db_dependency, submission: SubmissionCreate = Body(..., description="The submission details for creating a new submission.", example={
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "model_id": "123e4567-e89b-12d3-a456-426614174000",
    "challenge_id": "123e4567-e89b-12d3-a456-426614174000",
    "description": "This is a description of the submission",
    "dataset_url": "https://my-bucket.s3.amazonaws.com/my-dataset.zip"
} )):
    try:
        submission_instance = models.Submission(**submission.model_dump())
        db.add(submission_instance)
        db.commit()
        db.refresh(submission_instance)
        return submission_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(db: db_dependency, submission_id: uuid.UUID = Path(..., description="This is the ID of the submission")):
    try:
        submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        # Database CASCADE will automatically delete related results
        db.delete(submission)
        db.commit()
        
        return {"message": "Submission and related records deleted successfully"}
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        # Return detailed error information
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to delete submission",
                "message": str(e),
                "submission_id": str(submission_id),
                "error_type": type(e).__name__
            }
        )

# ******** basic endpoints ********


# ******** upload json file ********
@router.post("/create-submission", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def create_submission(
    db: db_dependency,
    file: UploadFile = File(..., description="JSON file containing inference results with 'filename' and 'prediction' columns"),
    user_id: uuid.UUID = Form(..., description="ID of the user uploading the file"),
    model_name: str = Form(..., description="Name of the model used for inference"),
    challenge_id: uuid.UUID = Form(..., description="ID of the challenge for evaluation"),
    description: str = Form(..., description="Description of the submission")
):
    """
    Upload and validate a JSON file containing ML inference results.
    
    The JSON file must contain 'filename' and 'prediction' columns.
    If validation passes, the file is uploaded to S3 and metadata is stored in the database.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.json'):
            raise HTTPException(
                status_code=400,
                detail="Only JSON files are allowed"
            )
        
        file_content = await file.read()
        
        # Validate file size (limit to 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail="File size exceeds 50MB limit"
            )

        # Create or get model record in database first
        model_instance = create_or_get_model(db, model_name, user_id)
        
        # Fetch challenge name for S3 path organization
        challenge_instance = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
        if not challenge_instance:
            raise HTTPException(
                status_code=404,
                detail=f"Challenge with ID {challenge_id} not found"
            )
        challenge_name = challenge_instance.title
        
        # Create submission record in database (without dataset_url initially)
        submission_data = {
            "user_id": user_id,
            "model_id": model_instance.id,
            "challenge_id": challenge_id,
            "description": description,
            "dataset_url": None  # Will be updated after S3 upload
        }
        
        submission_instance = models.Submission(**submission_data)
        db.add(submission_instance)
        db.commit()
        db.refresh(submission_instance)
        
        # Now process the file with submission ID for S3 versioning
        success, message, s3_url, json_data = await process_json_file_upload(
            file_content, file.filename, user_id, model_instance.id, submission_instance.id, challenge_name
        )

        if not success:
            # Rollback the submission if upload fails
            db.delete(submission_instance)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "File validation or upload failed",
                    "message": message,
                    "filename": file.filename
                }
            )
        
        # Update submission record with S3 URL
        submission_instance.dataset_url = s3_url
        db.commit()
        db.refresh(submission_instance)
        
        # Calculate some basic statistics about the uploaded data
        record_count = len(json_data) if isinstance(json_data, list) else 1
        
        # Return the submission instance which matches SubmissionRead schema
        return submission_instance
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error during file processing",
                "message": str(e),
                "filename": file.filename if file else "unknown"
            }
        )