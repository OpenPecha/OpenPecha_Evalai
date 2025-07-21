from fastapi import FastAPI, status, HTTPException, Depends, Path
from typing import Annotated, List
import models
from database import create_table, get_db
from sqlalchemy.orm import Session
from schemas import ChallengeCreate, ChallengeRead, UserCreate, UserRead

app = FastAPI()
create_table()

db_dependency = Annotated[Session, Depends(get_db)]

# --- Endpoints for users---

@app.get("/users/", response_model=List[UserRead], status_code=status.HTTP_200_OK)
async def list_all_users(db: db_dependency):
    try:
        return db.query(models.User).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
async def get_user(db: db_dependency, user_id: int = Path(gt=0)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_new_user(user: UserCreate, db: db_dependency):
    try:
        user_instance = models.User(**user.model_dump())
        db.add(user_instance)
        db.commit()
        db.refresh(user_instance)
        return user_instance
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db: db_dependency, user_id: int = Path(gt=0)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    hosted_challenges = db.query(models.Challenge).filter(models.Challenge.hosted_by == user_id).count()
    if hosted_challenges > 0:
        raise HTTPException(status_code=400, detail="User cannot be deleted because they are hosting one or more challenges.")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


# --- Endpoints for challenges---

@app.get("/challenges/", response_model=List[ChallengeRead])
async def list_all_challenges(db: db_dependency):
    try:
        return db.query(models.Challenge).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/challenges/{challenge_id}", response_model=ChallengeRead)
async def get_challenge(db: db_dependency, challenge_id: int = Path(gt=0)):
    challenge = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge


@app.post("/challenges/", response_model=ChallengeRead, status_code=status.HTTP_201_CREATED)
async def create_new_challenge(challenge: ChallengeCreate, db: db_dependency):
    try:
        challenge_instance = models.Challenge(**challenge.model_dump())
        db.add(challenge_instance)
        db.commit()
        db.refresh(challenge_instance)
        return challenge_instance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/challenges/{challenge_id}", response_model=ChallengeRead)
async def update_challenge(challenge_update: ChallengeCreate, db: db_dependency, challenge_id: int = Path(gt=0)):
    challenge = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    for key, value in challenge_update.model_dump().items():
        setattr(challenge, key, value)
    db.commit()
    db.refresh(challenge)
    return challenge

@app.delete("/challenges/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_challenge(db: db_dependency, challenge_id: int = Path(gt=0)):
    challenge = db.query(models.Challenge).filter(models.Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    db.delete(challenge)
    db.commit()
    return {"message": "Challenge deleted successfully"}