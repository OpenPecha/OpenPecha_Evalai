from fastapi import APIRouter, status, HTTPException, Depends, Path, Body
from typing import Annotated, List
from sqlalchemy.orm import Session
from models import Challenge
from database import get_db
from schemas.challenge import ChallengeCreate, ChallengeRead, ChallengeUpdate, ChallengeWithCategoryRead
from uuid import UUID
from sqlalchemy.orm import joinedload


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
    challenge: ChallengeCreate = Body(
        ...,
        description="The challenge details for creating a new challenge",
        example={
            "title": "OCR Challenge 2025",
            "image_uri": "https://example.com/challenge-image.png",
            "category_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
            "created_by": "c1d2e3f4-5678-4abc-9def-1234567890ab",
            "ground_truth": "https://s3.amazonaws.com/bucket/ground_truth.json",
            "description": "Recognize Tibetan script in scanned documents.",
            "status": "active"
        }
    )
):
    try:
        challenge_instance = Challenge(**challenge.model_dump())
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
    challenge_id: UUID = Path(..., description="This is the ID of the challenge to update"),
    challenge_update: ChallengeUpdate = Body(..., description="The fields to update for the challenge")
):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    update_data = challenge_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(challenge, field, value)
    db.commit()
    db.refresh(challenge)
    return challenge

# for deleting a challenge

@router.delete("/{challenge_id}", status_code=status.HTTP_200_OK)
async def delete_challenge(db: db_dependency, challenge_id: UUID = Path(..., description="This is the ID of the challenge to delete")):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    db.delete(challenge)
    db.commit()
    return {"message": "Challenge deleted successfully"}