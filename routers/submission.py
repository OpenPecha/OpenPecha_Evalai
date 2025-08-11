from fastapi import APIRouter, status, HTTPException, Depends, Path, Body, UploadFile, File, Form
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from models.user import User
from models.submission import SubmissionStatus
from database import get_db
from schemas.submission import SubmissionCreate, SubmissionRead, SubmissionCreatedResponse, SubmissionStatusResponse
from CRUD.model import create_or_get_model
from background_tasks import start_submission_processing, get_task_status
import logging
from auth import get_current_active_user
import uuid

# Constants for repeated strings
SUBMISSION_ID_PATH_DESCRIPTION = "This is the ID of the submission"
SUBMISSION_NOT_FOUND_MESSAGE = "Submission not found"

router = APIRouter(prefix="/submissions", tags=["submissions"])

db_dependency = Annotated[Session, Depends(get_db)]

# ******** basic endpoints ********
@router.get("", response_model=List[SubmissionRead])
async def list_all_submissions(db: db_dependency):
    """List all submissions (admin only - for now open to all)."""
    try:
        return db.query(models.Submission).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my", response_model=List[SubmissionRead])
async def list_my_submissions(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user)
):
    """List submissions created by the current authenticated user."""
    try:
        return db.query(models.Submission).filter(models.Submission.user_id == current_user.id).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{submission_id}", response_model=SubmissionRead)
async def get_submission(db: db_dependency, submission_id: uuid.UUID = Path(..., description=SUBMISSION_ID_PATH_DESCRIPTION)):
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail=SUBMISSION_NOT_FOUND_MESSAGE)
    return submission

@router.get("/{submission_id}/status", response_model=SubmissionStatusResponse)
async def get_submission_status(
    db: db_dependency, 
    submission_id: uuid.UUID = Path(..., description=SUBMISSION_ID_PATH_DESCRIPTION)
):
    """
    Get the current processing status of a submission.
    
    Use this endpoint to track the progress of your submission after creation.
    
    Status values:
    - pending: Submission created, waiting to start processing
    - processing: File upload and evaluation in progress
    - completed: All processing completed successfully
    - failed: Processing failed, check status_message for details
    """
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail=SUBMISSION_NOT_FOUND_MESSAGE)
    
    # Check if background task is still running
    task_running = get_task_status(str(submission_id))
    
    # If task is running but status shows completed/failed, there might be a sync issue
    if task_running and submission.status in [SubmissionStatus.COMPLETED, SubmissionStatus.FAILED]:
        # Update to processing if task is still running
        submission.status = SubmissionStatus.PROCESSING
        submission.status_message = "Processing in progress..."
        db.commit()
    
    return SubmissionStatusResponse(
        id=submission.id,
        status=submission.status,
        status_message=submission.status_message,
        created_at=submission.created_at,
        updated_at=submission.updated_at
    )



@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    submission_id: uuid.UUID = Path(..., description=SUBMISSION_ID_PATH_DESCRIPTION)
):
    try:
        submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
        if not submission:
            raise HTTPException(status_code=404, detail=SUBMISSION_NOT_FOUND_MESSAGE)
        
        # Check if the current user is the owner of the submission
        if submission.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only delete your own submissions")
        
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
@router.post("/create-submission", response_model=SubmissionCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_submission(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user),
    file: UploadFile = File(..., description="JSON file containing inference results with 'filename' and 'prediction' columns"),
    model_name: str = Form(..., description="Name of the model used for inference (you can add new model name and it will create in our model table only if the submission file passes the validation.)"),
    challenge_id: uuid.UUID = Form(..., description="ID of the challenge for evaluation (basically holds the ground truth file)"),
    description: str = Form(..., description="Description of the submission (will come from front end)")
):
    """
    Upload and validate a JSON file containing ML inference results.
    
    This endpoint returns immediately with a submission ID. The file processing and evaluation
    happen asynchronously in the background. Use the status endpoint to track progress.

    The JSON file must contain 'filename' and 'prediction' columns.

    Example usage:
    - file: inference_results.json
    - user_id: (automatically extracted from authentication token)
    - model_name: my-awesome-model
    - challenge_id: 123e4567-e89b-12d3-a456-426614174000
    - description: This is a description of the submission

    Returns:
    - submission_id: Use this to track the status
    - status: Current status (will be 'pending' initially)
    - message: Status message
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
        model_instance = create_or_get_model(db, model_name, current_user.id)
        
        # Fetch challenge for validation and get name
        challenge_instance = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
        if not challenge_instance:
            raise HTTPException(
                status_code=404,
                detail=f"Challenge with ID {challenge_id} not found"
            )
        challenge_name = challenge_instance.title
        
        # Create submission record in database with pending status
        submission_data = {
            "user_id": current_user.id,
            "model_id": model_instance.id,
            "challenge_id": challenge_id,
            "description": description,
            "dataset_url": None,  # Will be updated after S3 upload
            "status": SubmissionStatus.PENDING,
            "status_message": "Submission created, processing will begin shortly..."
        }
        
        submission_instance = models.Submission(**submission_data)
        db.add(submission_instance)
        db.commit()
        db.refresh(submission_instance)
        
        # Start background processing
        task_started = start_submission_processing(
            str(submission_instance.id),
            file_content,
            file.filename,
            current_user.id,
            str(model_instance.id),
            challenge_name,
            challenge_instance.ground_truth
        )
        
        if not task_started:
            # If we couldn't start the background task, mark as failed
            submission_instance.status = SubmissionStatus.FAILED
            submission_instance.status_message = "Failed to start background processing"
            db.commit()
            
            raise HTTPException(
                status_code=500,
                detail="Failed to start background processing for submission"
            )
        
        # Return immediate response with submission ID
        return SubmissionCreatedResponse(
            id=submission_instance.id,
            status=submission_instance.status,
            message="Submission created successfully. Use the status endpoint to track progress."
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error during submission creation",
                "message": str(e),
                "filename": file.filename if file else "unknown"
            }
        )