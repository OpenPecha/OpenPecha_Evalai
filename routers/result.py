from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
from database import get_db
from schemas.result import ResultCreate, ResultRead, ResultReadNested
import uuid
from models.result import Result

router = APIRouter(prefix="/results", tags=["results"])

db_dependency = Annotated[Session, Depends(get_db)]


# ** result (submission_id) -> submission (model_id) -> model **
from models.submission import Submission
from models.model import Model

@router.get("/leaderboard", response_model=List[ResultReadNested], status_code=status.HTTP_200_OK)
async def get_leaderboard(db: db_dependency):
    results = db.query(Result).all()
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

@router.post("/create", response_model=ResultRead, status_code=status.HTTP_201_CREATED)
async def create_result(
    db: db_dependency,
    result: ResultCreate = Body(..., description="The result details for creating a new result.")
):
    if result.score < 0:
        raise HTTPException(status_code=400, detail="Score must be non-negative.")
    try:
        result_instance = Result(**result.model_dump())
        db.add(result_instance)
        db.commit()
        db.refresh(result_instance)
        return result_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

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

@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result(db: db_dependency, result_id: uuid.UUID = Path(gt=0)):
    result = db.query(Result).filter(Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}

# ********* basic CRUD operations ends here *************