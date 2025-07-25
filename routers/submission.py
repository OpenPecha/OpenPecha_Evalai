from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas.submission import SubmissionCreate, SubmissionRead
import uuid

router = APIRouter(prefix="/submissions", tags=["submissions"])

db_dependency = Annotated[Session, Depends(get_db)]

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
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    db.delete(submission)
    db.commit()
    return {"message": "Submission deleted successfully"}
