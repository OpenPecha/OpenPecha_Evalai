from sqlalchemy.orm import Session
from uuid import UUID
import models
from database import get_db
from typing import Optional, Annotated
from fastapi import Depends

db_dependency = Annotated[Session, Depends(get_db)]

def create_or_get_model(db: db_dependency, model_name: str, user_id: UUID) -> models.Model:
    """
    Create a new model or get an existing model by name.
    
    This function checks if a model with the given name already exists.
    If it exists, returns the existing model.
    If it doesn't exist, creates a new model record.
    
    Args:
        db: Database session
        model_name: Name of the model
        user_id: ID of the user creating the model
        
    Returns:
        Model: The existing or newly created model instance
    """
    # Check if model with this name already exists
    existing_model = db.query(models.Model).filter(
        models.Model.name == model_name
    ).first()
    
    if existing_model:
        # Return existing model
        return existing_model
    
    # Create new model if it doesn't exist
    new_model = models.Model(
        name=model_name,
        created_by=str(user_id),  # Convert UUID to string
        updated_by=str(user_id)   # Convert UUID to string
    )
    
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    
    return new_model