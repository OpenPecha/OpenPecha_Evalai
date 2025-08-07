from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from models.user import User
from database import get_db
from schemas.result import ResultCreate, ResultRead
from auth import get_current_active_user
import uuid

router = APIRouter(prefix="/results", tags=["results"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("", response_model=List[ResultRead])
async def list_all_results(db: db_dependency):
    try:
        return db.query(models.Result).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{result_id}", response_model=ResultRead)
async def get_result(db: db_dependency, result_id: uuid.UUID = Path(..., description="This is the ID of the result")):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()
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
        result_instance = models.Result(**result_data)
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
    result_id: uuid.UUID = Path(..., description="This is the ID of the result")
):
    """Delete a result. Only the owner can delete their own results."""
    result = db.query(models.Result).filter(models.Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    # Only allow the owner to delete the result
    if result.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own results")
    
    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}
