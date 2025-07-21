from fastapi import APIRouter, status, HTTPException, Depends, Path
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas.result import ResultCreate, ResultRead

router = APIRouter(prefix="/results", tags=["results"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/", response_model=List[ResultRead])
async def list_all_results(db: db_dependency):
    try:
        return db.query(models.Result).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{result_id}", response_model=ResultRead)
async def get_result(db: db_dependency, result_id: int = Path(gt=0)):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result

@router.post("/", response_model=ResultRead, status_code=status.HTTP_201_CREATED)
async def create_new_result(result: ResultCreate, db: db_dependency):
    try:
        result_instance = models.Result(**result.model_dump())
        db.add(result_instance)
        db.commit()
        db.refresh(result_instance)
        return result_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result(db: db_dependency, result_id: int = Path(gt=0)):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}
