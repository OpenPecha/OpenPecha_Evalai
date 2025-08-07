from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
from models import Challenge
from models.user import User
from database import get_db
from schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeUpdate, ChallengeWithCategoryRead
from uuid import UUID
from sqlalchemy.orm import joinedload
from auth import get_current_active_user


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

# for creating a new challenge

@router.post("/create", response_model=ChallengeRead, status_code=status.HTTP_201_CREATED)
async def create_new_challenge(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user),
    challenge: ChallengeCreate = Body(
        ...,
        description="The challenge details for creating a new challenge",
        example={
            "title": "OCR Challenge 2025",
            "image_uri": "https://example.com/challenge-image.png",
            "category_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
            "ground_truth": "https://s3.amazonaws.com/bucket/ground_truth.json",
            "description": "Recognize Tibetan script in scanned documents.",
            "status": "active"
        }
    )
):
    """Create a new challenge. The creator is determined from the authenticated user token."""
    try:
        # Add created_by from authenticated user
        challenge_data = challenge.model_dump()
        challenge_data['created_by'] = current_user.id
        challenge_instance = Challenge(**challenge_data)
        db.add(challenge_instance)
        db.commit()
        db.refresh(challenge_instance)
        return challenge_instance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# for updating a challenge

@router.patch("/{challenge_id}", response_model=ChallengeRead, status_code=status.HTTP_200_OK)
async def update_challenge(
    db: db_dependency,
    current_user: User = Depends(get_current_active_user),
    challenge_id: UUID = Path(..., description="This is the ID of the challenge to update"),
    challenge_update: ChallengeUpdate = Body(..., description="The fields to update for the challenge")
):
    """Update a challenge. Only the creator can update their own challenges."""
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Only allow the creator to update the challenge
    if challenge.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update challenges you created")
    
    update_data = challenge_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(challenge, field, value)
    db.commit()
    db.refresh(challenge)
    return challenge

# for deleting a challenge

@router.delete("/{challenge_id}", status_code=status.HTTP_200_OK)
async def delete_challenge(
    db: db_dependency, 
    current_user: User = Depends(get_current_active_user),
    challenge_id: UUID = Path(..., description="This is the ID of the challenge to delete")
):
    """Delete a challenge. Only the creator can delete their own challenges."""
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Only allow the creator to delete the challenge
    if challenge.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete challenges you created")
    
    db.delete(challenge)
    db.commit()
    return {"message": "Challenge deleted successfully"}