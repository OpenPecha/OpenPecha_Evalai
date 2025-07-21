from fastapi import APIRouter, status, HTTPException, Depends, Path
from typing import Annotated, List
from sqlalchemy.orm import Session
import models
from database import get_db
from schemas.challenge import ChallengeCreate, ChallengeRead

router = APIRouter(prefix="/challenges", tags=["challenges"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/", response_model=List[ChallengeRead])
async def list_all_challenges(db: db_dependency):
    try:
        return db.query(models.Challenge).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{challenge_id}", response_model=ChallengeRead)
async def get_challenge(db: db_dependency, challenge_id: int = Path(gt=0)):
    challenge = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge

@router.post("/", response_model=ChallengeRead, status_code=status.HTTP_201_CREATED)
async def create_new_challenge(challenge: ChallengeCreate, db: db_dependency):
    try:
        challenge_instance = models.Challenge(**challenge.model_dump())
        db.add(challenge_instance)
        db.commit()
        db.refresh(challenge_instance)
        return challenge_instance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{challenge_id}", response_model=ChallengeRead)
async def update_challenge(db: db_dependency, challenge_id: int = Path(gt=0), challenge_update: ChallengeCreate = None):
    challenge = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    for key, value in challenge_update.model_dump().items():
        setattr(challenge, key, value)
    db.commit()
    db.refresh(challenge)
    return challenge

@router.delete("/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_challenge(db: db_dependency, challenge_id: int = Path(gt=0)):
    challenge = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    db.delete(challenge)
    db.commit()
    return {"message": "Challenge deleted successfully"}
