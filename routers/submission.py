from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from models.user import User
from database import get_db
from schemas.submission import SubmissionCreate, SubmissionRead
from auth import get_current_active_user
import uuid

router = APIRouter(prefix="/submissions", tags=["submissions"])

db_dependency = Annotated[Session, Depends(get_db)]

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
async def get_submission(db: db_dependency, submission_id: uuid.UUID = Path(..., description="This is the ID of the submission")):
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission

@router.post("/create", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def create_new_submission(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    submission: SubmissionCreate = Body(..., description="The submission details for creating a new submission.", example={
        "model_id": "123e4567-e89b-12d3-a456-426614174000",
        "description": "This is a description of the submission",
        "dataset_url": "https://my-bucket.s3.amazonaws.com/my-dataset.zip"
    })
):
    """Create a new submission. The user is determined from the authenticated token."""
    try:
        # Add user_id from authenticated user
        submission_data = submission.model_dump()
        submission_data['user_id'] = current_user.id
        submission_instance = models.Submission(**submission_data)
        db.add(submission_instance)
        db.commit()
        db.refresh(submission_instance)
        return submission_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    submission_id: uuid.UUID = Path(..., description="This is the ID of the submission")
):
    """Delete a submission. Only the owner can delete their own submissions."""
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Only allow the owner to delete the submission
    if submission.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own submissions")
    
    db.delete(submission)
    db.commit()
    return {"message": "Submission deleted successfully"}
