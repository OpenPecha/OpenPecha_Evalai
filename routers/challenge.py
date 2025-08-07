from fastapi import APIRouter, status, HTTPException, Depends, Path, Body, UploadFile, File, Form
from typing import Annotated, List, Optional
from sqlalchemy.orm import Session
from models import Challenge
from models.user import User
from database import get_db
from schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeWithCategoryRead
from uuid import UUID
from sqlalchemy.orm import joinedload
from CRUD.ground_truth_upload_s3 import process_ground_truth_file
import logging
import uuid
from datetime import datetime


router = APIRouter(prefix="/challenges", tags=["challenges"])

db_dependency = Annotated[Session, Depends(get_db)]


# for listing all challenges

@router.get("/list", response_model=List[ChallengeWithCategoryRead])
async def list_challenges_with_category(db: db_dependency):
    try:
        # Eager load the category relationship
        challenges = db.query(Challenge).options(joinedload(Challenge.category)).all()
        return challenges
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# for getting a specific challenge

@router.get("/{challenge_id}", response_model=ChallengeRead)
async def get_challenge(db: db_dependency, challenge_id: UUID = Path(..., description="This is the ID of the challenge")):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge

# For creating a new challenge with ground truth file.

@router.post("/create", response_model=ChallengeRead, status_code=status.HTTP_201_CREATED)
async def create_new_challenge(
    db: db_dependency,
    title: str = Form(..., description="Challenge title"),
    category_id: UUID = Form(..., description="Category ID"),
    created_by: UUID = Form(..., description="User ID who created the challenge"),
    image_uri: Optional[str] = Form(None, description="Challenge image URL"),
    description: Optional[str] = Form(None, description="Challenge description"),
    status: Optional[str] = Form("active", description="Challenge status"),
    ground_truth_file: Optional[UploadFile] = File(None, description="Ground truth JSON file")
):
    """
    Create a new challenge with optional ground truth file upload.
    
    If ground_truth_file is provided, it will be uploaded to S3 and the URL will be stored.
    If not provided, the ground_truth field will be left empty and can be added later via update.
    """
    try:
        logging.info(f"Creating new challenge: {title}")
        
        # Create challenge instance without ground_truth initially
        challenge_data = {
            "title": title,
            "category_id": category_id,
            "created_by": created_by,
            "image_uri": image_uri,
            "description": description,
            "status": status,
            "ground_truth": ""  # Will be updated if file is provided
        }
        
        challenge_instance = Challenge(**challenge_data)
        db.add(challenge_instance)
        db.flush()  # Get the ID without committing
        
        # Handle ground truth file upload if provided
        if ground_truth_file and ground_truth_file.filename:
            logging.info(f"Processing ground truth file: {ground_truth_file.filename}")
            
            # Use CRUD function to handle all file processing
            success, message, s3_url = await process_ground_truth_file(
                file=ground_truth_file,
                challenge_id=challenge_instance.id,
                challenge_title=title
            )
            
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=message
                )
            
            # Update challenge with ground truth URL
            challenge_instance.ground_truth = s3_url
            logging.info(f"Ground truth uploaded successfully: {s3_url}")
        
        # Commit the challenge
        db.commit()
        db.refresh(challenge_instance)
        
        logging.info(f"Challenge created successfully: {challenge_instance.id}")
        return challenge_instance
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Unexpected error creating challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# for updating a challenge

@router.patch("/update/{challenge_id}", response_model=ChallengeRead, status_code=status.HTTP_200_OK)
async def update_challenge(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user),
    challenge_id: UUID = Path(..., description="This is the ID of the challenge to update"),
    title: Optional[str] = Form(None, description="Challenge title"),
    category_id: Optional[str] = Form(None, description="Category ID"),
    image_uri: Optional[str] = Form(None, description="Challenge image URL"),
    description: Optional[str] = Form(None, description="Challenge description"),
    status: Optional[str] = Form(None, description="Challenge status"),
    ground_truth_file: Optional[UploadFile] = File(None, description="Ground truth JSON file to replace existing one (or you can leave empty. do not check box send empty value)")
):
    """
    Update an existing challenge with optional ground truth file upload.
    
    If ground_truth_file is provided, it will replace the existing ground truth file.
    Other fields are optional and will only be updated if provided.
    """
    try:
        logging.info(f"Updating challenge: {challenge_id}")
        
        # Find existing challenge
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Convert empty strings to None for all optional fields to preserve existing data
        if title == "":
            title = None
        if category_id == "":
            category_id = None
        elif category_id is not None:
            try:
                category_id = UUID(category_id)  # Convert string to UUID
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid UUID format for category_id")
        if image_uri == "":
            image_uri = None
        if description == "":
            description = None
        if status == "":
            status = None
        
        # Update basic fields if provided
        if title is not None:
            challenge.title = title
        if category_id is not None:
            challenge.category_id = category_id
        if image_uri is not None:
            challenge.image_uri = image_uri
        if description is not None:
            challenge.description = description
        if status is not None:
            challenge.status = status
        
        # Handle ground truth file upload if provided
        if ground_truth_file and ground_truth_file.filename:
            logging.info(f"Processing new ground truth file: {ground_truth_file.filename}")
            
            # Use CRUD function to handle all file processing
            success, message, s3_url = await process_ground_truth_file(
                file=ground_truth_file,
                challenge_id=challenge_id,
                challenge_title=challenge.title
            )
            
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=message
                )
            
            # Update challenge with new ground truth URL
            challenge.ground_truth = s3_url
            logging.info(f"Ground truth updated successfully: {s3_url}")
        
        # Commit changes
        db.commit()
        db.refresh(challenge)
        
        logging.info(f"Challenge updated successfully: {challenge_id}")
        return challenge
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Unexpected error updating challenge {challenge_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# for deleting a challenge

@router.delete("/remove/{challenge_id}", status_code=status.HTTP_200_OK)
async def delete_challenge(db: db_dependency, challenge_id: UUID = Path(..., description="This is the ID of the challenge to delete")):
    """
    Delete a challenge by ID and return confirmation.
    
    Returns a confirmation message with details about the deleted challenge.
    """
    try:
        logging.info(f"Attempting to delete challenge: {challenge_id}")
        
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            logging.warning(f"Challenge not found for deletion: {challenge_id}")
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        challenge_title = challenge.title
        challenge_created_at = challenge.created_at
        
        db.delete(challenge)
        db.commit()
        
        logging.info(f"Challenge deleted successfully: {challenge_id} - {challenge_title}")
        
        return {
            "message": "Challenge deleted successfully",
            "deleted_challenge": {
                "id": str(challenge_id),
                "title": challenge_title,
                "created_at": challenge_created_at.isoformat(),
                "deleted_at": datetime.now().isoformat()
            },
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Unexpected error deleting challenge {challenge_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
