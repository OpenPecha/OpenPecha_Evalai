from fastapi import APIRouter, status, HTTPException, Depends, Path
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/", response_model=List[UserRead], status_code=status.HTTP_200_OK)
async def list_all_users(db: db_dependency):
    try:
        return db.query(models.User).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user(db: db_dependency, user_id: int = Path(gt=0)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/create/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_new_user(db: db_dependency, user: UserCreate):
    try:
        user_instance = models.User(**user.model_dump())
        db.add(user_instance)
        db.commit()
        db.refresh(user_instance)
        return user_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db: db_dependency, user_id: int = Path(gt=0)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    hosted_challenges = db.query(models.Challenge).filter(models.Challenge.hosted_by == user_id).count()
    if hosted_challenges > 0:
        raise HTTPException(status_code=400, detail="User cannot be deleted because they are hosting one or more challenges.")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}
