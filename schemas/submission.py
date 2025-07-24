import uuid
import datetime
from pydantic import BaseModel
from typing import Optional

class SubmissionBase(BaseModel):
    user_id: uuid.UUID
    model_id: uuid.UUID
    description: Optional[str] = None
    dataset_url: Optional[str] = None

class SubmissionCreate(SubmissionBase):
    pass

class SubmissionRead(SubmissionBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
