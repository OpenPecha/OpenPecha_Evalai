from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
from database import get_db
from schemas.result import ResultCreate, ResultRead, ResultReadNested
import uuid
from models.result import Result
from models.user import User
from auth import get_current_active_user

router = APIRouter(prefix="/results", tags=["results"])

db_dependency = Annotated[Session, Depends(get_db)]


# ** result (submission_id) -> submission (model_id) -> model **
from models.submission import Submission
from models.model import Model

@router.get("/challenge/{challenge_id}", response_model=List[ResultReadNested], status_code=status.HTTP_200_OK)
async def get_results_by_challenge(
    db: db_dependency,
    challenge_id: uuid.UUID = Path(..., description="Challenge ID to get results for")
):
    """Get all results for a specific challenge"""
    # Get all submissions for the challenge
    submissions = db.query(Submission).filter(Submission.challenge_id == challenge_id).all()
    
    if not submissions:
        return []
    
    # Get submission IDs
    submission_ids = [submission.id for submission in submissions]
    
    # Get all results for these submissions
    results = db.query(Result).filter(Result.submission_id.in_(submission_ids)).all()
    
    nested_results = []
    for result in results:
        submission = db.query(Submission).filter(Submission.id == result.submission_id).first()
        if not submission:
            continue
        model = db.query(Model).filter(Model.id == submission.model_id).first()
        if not model:
            continue
        
        model_data = {
            'id': model.id,
            'name': model.name,
            'created_at': model.created_at,
            'created_by': model.created_by,
            'updated_at': model.updated_at,
            'updated_by': model.updated_by
        }
        submission_data = {
            'id': submission.id,
            'user_id': submission.user_id,
            'model_id': submission.model_id,
            'description': submission.description,
            'dataset_url': submission.dataset_url,
            'created_at': submission.created_at,
            'updated_at': submission.updated_at,
            'model': model_data
        }
        result_data = {
            'id': result.id,
            'type': result.type,
            'user_id': result.user_id,
            'submission_id': result.submission_id,
            'score': result.score,
            'created_by': result.created_by,
            'updated_by': result.updated_by,
            'created_at': result.created_at,
            'updated_at': result.updated_at,
            'submission': submission_data
        }
        nested_results.append(result_data)
    
    return nested_results

# ************ basic CRUD operations **************

@router.get("", response_model=List[ResultRead])
async def list_all_results(db: db_dependency):
    try:
        return db.query(Result).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{result_id}", response_model=ResultRead)
async def get_result(db: db_dependency, result_id: uuid.UUID = Path(gt=0)):
    result = db.query(Result).filter(Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result

@router.post("/create", response_model=ResultRead, status_code=status.HTTP_201_CREATED)
async def create_new_result(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user),
    result: ResultCreate = Body(..., description="The result details for creating a new result.", example={
        "type": "WER",
        "submission_id": "123e4567-e89b-12d3-a456-426614174000",
        "score": 0.85
    })
):
    """Create a new result. The user is determined from the authenticated token."""
    try:
        # Add user_id and audit fields from authenticated user
        result_data = result.model_dump()
        result_data['user_id'] = current_user.id
        result_data['created_by'] = current_user.username
        result_data['updated_by'] = current_user.username
        result_instance = Result(**result_data)
        db.add(result_instance)
        db.commit()
        db.refresh(result_instance)
        return result_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    result_id: uuid.UUID = Path(..., description="ID of the result to delete")
):
    result = db.query(Result).filter(Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    # Only allow the owner to delete the result
    if result.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own results")
    
    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}

# ********* basic CRUD operations ends here *************