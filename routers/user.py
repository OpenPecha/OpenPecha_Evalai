from fastapi import APIRouter, status, HTTPException, Depends, Path
from typing import Annotated, List
from sqlalchemy.orm import Session
from models.user import User
from models.challenge import Challenge
from database import get_db
from schemas.user import UserCreate, UserRead, UserUpdate
from fastapi import Body
import uuid

router = APIRouter(prefix="/users", tags=["users"])

db_dependency = Annotated[Session, Depends(get_db)]

# for listing all users

@router.get("", response_model=List[UserRead], status_code=status.HTTP_200_OK)
async def list_all_users(db: db_dependency):
    try:
        return db.query(User).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user(db: db_dependency, user_id: uuid.UUID = Path(..., description="This is the ID of the user")):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# for creating new user

@router.post("/create", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_new_user(db: db_dependency, user: UserCreate = Body(
        ..., 
        description="The user details for creating a new user.",
        example={
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "picture": "http://example.com/pic.jpg",
            "role": "admin"
        }
    )):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    try:
        user_instance = User(**user.model_dump())
        db.add(user_instance)
        db.commit()
        db.refresh(user_instance)
        return user_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="an error occurred while creating the user: " + str(e))

# for deleting user

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(db: db_dependency, user_id: uuid.UUID = Path(..., description="This is the ID of the user")):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

# for updating user

@router.patch("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def update_user(
    db: db_dependency,
    user_id: uuid.UUID = Path(..., description="This is the ID of the user to update"),
    user_update: UserUpdate = Body(..., description="The fields to update for the user")
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user

