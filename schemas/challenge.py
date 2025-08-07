import uuid
import datetime
from pydantic import BaseModel
from typing import Optional
from schemas.category import CategoryRead

class ChallengeBase(BaseModel):
    title: str
    image_uri: Optional[str] = None
    category_id: uuid.UUID
    created_by: str  # Updated to string for Auth0 user ID
    ground_truth: str  # URL to ground truth JSON file
    description: Optional[str] = None # it is optional for now.
    status: Optional[str] = None # it is optional for now.

class ChallengeCreate(BaseModel):
    title: str
    image_uri: Optional[str] = None
    category_id: uuid.UUID
    ground_truth: str  # URL to ground truth JSON file
    description: Optional[str] = None # it is optional for now.
    status: Optional[str] = None # it is optional for now.
    # created_by comes from authenticated user token

class ChallengeUpdate(BaseModel):
    title: Optional[str] = None
    image_uri: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    ground_truth: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    # created_by cannot be updated

class ChallengeRead(ChallengeBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class ChallengeWithCategoryRead(ChallengeRead):
    category: CategoryRead

    class Config:
        from_attributes = True
