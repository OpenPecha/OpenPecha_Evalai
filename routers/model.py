from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import List
from sqlalchemy.orm import Session
from database import get_db
from models.model import Model
from schemas.model import ModelCreate, ModelRead, ModelUpdate
import uuid
from typing import Annotated

router = APIRouter(prefix="/model", tags=["Model"])

db_dependency = Annotated[Session, Depends(get_db)]

# Create Model
@router.post("/", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
async def create_model(db: db_dependency, model: ModelCreate = Body(..., description="The model details for creating a new model.", example={
    "name": "Google Vision OCR",
    "created_by": "admin",
    "updated_by": "admin"
    }  )):
    try:
        model_instance = Model(**model.model_dump())
        db.add(model_instance)
        db.commit()
        db.refresh(model_instance)
        return model_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="An error occurred while creating the model: " + str(e))

# Get all Models
@router.get("/", response_model=List[ModelRead], status_code=status.HTTP_200_OK)
async def get_all_models(db: db_dependency):
    models = db.query(Model).all()
    return models

# Get Model by ID
@router.get("/{model_id}", response_model=ModelRead, status_code=status.HTTP_200_OK)
async def get_single_model(db: db_dependency, model_id: uuid.UUID = Path(..., description="ID of the model")):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

# Update Model
@router.patch("/{model_id}", response_model=ModelRead, status_code=status.HTTP_200_OK)
async def update_single_model(
    db: db_dependency,
    model_id: uuid.UUID = Path(..., description="ID of the model to update"),
    model_update: ModelUpdate = Body(..., description="Fields to update for the model")
):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    update_data = model_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(model, field, value)
    db.commit()
    db.refresh(model)
    return model

# Delete Model
@router.delete("/{model_id}", status_code=status.HTTP_200_OK)
async def delete_single_model(db: db_dependency, model_id: uuid.UUID = Path(..., description="ID of the model")):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    db.delete(model)
    db.commit()
    return {"message": "Model deleted successfully"}