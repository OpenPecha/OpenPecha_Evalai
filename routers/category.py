from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
from models.category import Category
from database import get_db
from schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from uuid import UUID

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
        raise HTTPException(status_code=404, detail="Category not found")
    return category

# for creating new category

@router.post("/create", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_new_category(db: db_dependency, category: CategoryCreate = Body(..., description="The category details for creating a new category.", example={
    "name": "OCR",
    "created_by": "admin",
    "updated_by": "admin"
    })):
    try:
        category_instance = Category(**category.model_dump())
        db.add(category_instance)
        db.commit()
        db.refresh(category_instance)
        return category_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# for deleting category

@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(db: db_dependency, category_id: UUID = Path(..., description="This is the ID of the category to delete")):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}

# for updating category

@router.patch("/{category_id}", response_model=CategoryRead, status_code=status.HTTP_200_OK)
async def update_category(db: db_dependency, category_id: UUID = Path(..., description="This is the ID of the category to update"), category_update: CategoryUpdate = Body(..., description="The fields to update for the category")):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category
