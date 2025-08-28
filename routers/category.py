from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
from models.category import Category
from models.user import User
from database import get_db
from schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from auth import get_current_active_user
from uuid import UUID

# Constants
CATEGORY_NOT_FOUND_MESSAGE = "Category not found"

router = APIRouter(prefix="/categories", tags=["categories"])

db_dependency = Annotated[Session, Depends(get_db)]

# for listing all categories

@router.get("", response_model=List[CategoryRead], status_code=status.HTTP_200_OK)
async def list_all_categories(db: db_dependency):
    try:
        return db.query(Category).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# for getting a specific category

@router.get("/{category_id}", response_model=CategoryRead, status_code=status.HTTP_200_OK)
async def get_category(db: db_dependency, category_id: UUID = Path(..., description="This is the ID of the category")):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail=CATEGORY_NOT_FOUND_MESSAGE)
    return category

# for creating new category

@router.post("/create", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_new_category(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    category: CategoryCreate = Body(..., description="The category details for creating a new category.", example={
        "name": "OCR"
    })
):
    try:
        # Check if category name already exists
        existing_category = db.query(Category).filter(Category.name == category.name).first()
        if existing_category:
            raise HTTPException(
                status_code=400, 
                detail=f"Category with name '{category.name}' already exists. Please choose a different name."
            )
        
        # Add user info from token to the category data
        category_data = category.model_dump()
        category_data['created_by'] = current_user.id
        category_data['updated_by'] = current_user.id
        
        category_instance = Category(**category_data)
        db.add(category_instance)
        db.commit()
        db.refresh(category_instance)
        return category_instance
    except HTTPException:
        # Re-raise HTTP exceptions as-is (like the duplicate name check)
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# for deleting category

@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    category_id: UUID = Path(..., description="This is the ID of the category to delete")
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail=CATEGORY_NOT_FOUND_MESSAGE)
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}

# for updating category

@router.patch("/{category_id}", response_model=CategoryRead, status_code=status.HTTP_200_OK)
async def update_category(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    category_id: UUID = Path(..., description="This is the ID of the category to update"), 
    category_update: CategoryUpdate = Body(..., description="The fields to update for the category")
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail=CATEGORY_NOT_FOUND_MESSAGE)
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category
