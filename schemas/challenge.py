import uuid
import datetime
from pydantic import BaseModel
from typing import Optional, Any

class ChallengeBase(BaseModel):
    title: str
    image_uri: Optional[str] = None
    category_id: uuid.UUID
    created_by: uuid.UUID
    ground_truth: str  # URL to ground truth JSON file
    description: Optional[str] = None # it is optional for now.
    status: Optional[str] = None # it is optional for now.

class ChallengeCreate(ChallengeBase):
    pass

class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    image_uri: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    ground_truth: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ChallengeRead(ChallengeBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
