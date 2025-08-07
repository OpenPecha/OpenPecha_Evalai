import uuid
import datetime
from pydantic import BaseModel, Field
from typing import Optional

class SubmissionBase(BaseModel):
    user_id: str = Field(..., description="ID of the user (Auth0 user ID)")
    model_id: uuid.UUID = Field(..., description="ID of the model")
    description: Optional[str] = Field(None, description="Description of the submission")
    dataset_url: Optional[str] = Field(None, description="Dataset URL of the submission")

class SubmissionCreate(BaseModel):
    model_id: uuid.UUID = Field(..., description="ID of the model")
    description: Optional[str] = Field(None, description="Description of the submission")
    dataset_url: Optional[str] = Field(None, description="Dataset URL of the submission")
    # user_id comes from authenticated token

class SubmissionUpdate(BaseModel):
    model_id: Optional[uuid.UUID] = Field(None, description="ID of the model from model table")
    description: Optional[str] = Field(None, description="Description of the submission")
    dataset_url: Optional[str] = Field(None, description="Dataset URL of the submission")
    # user_id cannot be updated

class SubmissionRead(SubmissionBase):
    id: uuid.UUID = Field(..., description="ID of the submission")
    created_at: datetime.datetime = Field(..., description="Creation timestamp of the submission")
    updated_at: datetime.datetime = Field(..., description="Last update timestamp of the submission")

    class Config:
        from_attributes = True
