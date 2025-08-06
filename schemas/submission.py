import uuid
import datetime
from pydantic import BaseModel, Field
from typing import Optional

class SubmissionBase(BaseModel):
    user_id: uuid.UUID = Field(..., description="ID of the user")
    model_id: uuid.UUID = Field(..., description="ID of the model")
    challenge_id: uuid.UUID = Field(..., description="ID of the challenge")
    description: Optional[str] = Field(None, description="Description of the submission")
    dataset_url: Optional[str] = Field(None, description="Dataset URL of the submission")

class SubmissionCreate(SubmissionBase):
    pass

class SubmissionUpdate(SubmissionBase):
    user_id: Optional[uuid.UUID] = Field(None, description="ID of the user from user table")
    model_id: Optional[uuid.UUID] = Field(None, description="ID of the model from model table")
    challenge_id: Optional[uuid.UUID] = Field(None, description="ID of the challenge")
    description: Optional[str] = Field(None, description="Description of the submission")
    dataset_url: Optional[str] = Field(None, description="Dataset URL of the submission")

class SubmissionRead(SubmissionBase):
    id: uuid.UUID = Field(..., description="ID of the submission")
    created_at: datetime.datetime = Field(..., description="Creation timestamp of the submission")
    updated_at: datetime.datetime = Field(..., description="Last update timestamp of the submission")

    class Config:
        from_attributes = True
