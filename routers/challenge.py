from fastapi import APIRouter, status, HTTPException, Depends, Path, Body, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Annotated, List, Optional
from sqlalchemy.orm import Session
import models
from models import Challenge
from models.user import User
from database import get_db
from schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeWithCategoryRead
from uuid import UUID
from sqlalchemy.orm import joinedload
from CRUD.ground_truth_upload_s3 import process_ground_truth_file
from auth import get_current_active_user
import logging
import uuid
import requests
import io
from datetime import datetime

# Constants
CHALLENGE_NOT_FOUND_MESSAGE = "Challenge not found"

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
        raise HTTPException(status_code=404, detail=CHALLENGE_NOT_FOUND_MESSAGE)
    return challenge

# for downloading ground truth file of a specific challenge

@router.get("/{challenge_id}/download-ground-truth")
async def download_ground_truth(
    db: db_dependency, 
    challenge_id: UUID = Path(..., description="This is the ID of the challenge")
):
    """
    Download the ground truth file for a specific challenge.
    
    Returns the ground truth JSON file as a downloadable attachment.
    """
    try:
        # Find the challenge
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise HTTPException(status_code=404, detail=CHALLENGE_NOT_FOUND_MESSAGE)
        
        # Check if ground truth URL exists
        if not challenge.ground_truth:
            raise HTTPException(
                status_code=404, 
                detail="Ground truth file not found for this challenge"
            )
        
        logging.info(f"Downloading ground truth for challenge {challenge_id}: {challenge.ground_truth}")
        
        # Download the file from S3 URL
        try:
            # Disable SSL verification for S3 URLs to avoid certificate issues with custom bucket names
            verify_ssl = False if 'amazonaws.com' in challenge.ground_truth else True
            response = requests.get(challenge.ground_truth, timeout=30, verify=verify_ssl)
            response.raise_for_status()  # Raises exception for bad status codes
            
            # Get file content
            file_content = response.content
            
            # Extract filename from URL or use default
            filename = f"ground_truth_{challenge.title.replace(' ', '_')}_{challenge_id}.json"
            if '/' in challenge.ground_truth:
                url_filename = challenge.ground_truth.split('/')[-1]
                if url_filename.endswith('.json'):
                    filename = url_filename
            
            # Create a streaming response
            return StreamingResponse(
                io.BytesIO(file_content),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Length": str(len(file_content))
                }
            )
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download ground truth from S3: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to download ground truth file: {str(e)}"
            )
        except Exception as e:
            logging.error(f"Unexpected error downloading ground truth: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error while downloading ground truth: {str(e)}"
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logging.error(f"Unexpected error in download_ground_truth endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# For creating a new challenge with ground truth file.

@router.post(
    "/create", 
    response_model=ChallengeRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new challenge",
    description="Create a new challenge with optional ground truth file upload"
)
async def create_new_challenge(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user),
    title: str = Form(..., description="Challenge title"),
    category_id: UUID = Form(..., description="Category ID"),
    image_uri: Optional[str] = Form(None, description="Challenge image URL"),
    description: Optional[str] = Form(None, description="Challenge description"),
    status: Optional[str] = Form("active", description="Challenge status"),
    ground_truth_file: UploadFile = File(None, description="Ground truth JSON file for the challenge (optional)")
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
            "created_by": current_user.id,  # Get user ID from authenticated token
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
    ground_truth_file: UploadFile = File(None, description="Ground truth JSON file to replace existing one (optional)")
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
            raise HTTPException(status_code=404, detail=CHALLENGE_NOT_FOUND_MESSAGE)
        
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
async def delete_challenge(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    challenge_id: UUID = Path(..., description="This is the ID of the challenge to delete")
):
    """
    Delete a challenge by ID and return confirmation.
    
    Authorization rules:
    - Admin users can delete any challenge
    - Non-admin users can only delete challenges they created
    
    Returns a confirmation message with details about the deleted challenge.
    """
    try:
        logging.info(f"Attempting to delete challenge: {challenge_id}")
        
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            logging.warning(f"Challenge not found for deletion: {challenge_id}")
            raise HTTPException(status_code=404, detail=CHALLENGE_NOT_FOUND_MESSAGE)
        
        # Check authorization: admin can delete any challenge, non-admin can only delete their own
        if current_user.role != 'admin' and challenge.created_by != current_user.id:
            logging.warning(f"User {current_user.id} attempted to delete challenge {challenge_id} owned by {challenge.created_by}")
            raise HTTPException(status_code=403, detail="You can only delete challenges you created")
        
        # Check if there are submissions referencing this challenge
        related_submissions = db.query(models.Submission).filter(models.Submission.challenge_id == challenge_id).all()
        if related_submissions:
            submission_count = len(related_submissions)
            logging.warning(f"Cannot delete challenge {challenge_id}: {submission_count} submissions reference it")
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete challenge. There are {submission_count} submission(s) that reference this challenge. Please delete all related submissions first."
            )
        
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
