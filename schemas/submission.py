import uuid
import datetime
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

# Constants for repeated strings
SUBMISSION_DESCRIPTION = "Description of the submission"
DATASET_URL_DESCRIPTION = "Dataset URL of the submission"
SUBMISSION_ID_DESCRIPTION = "ID of the submission"

class SubmissionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class SubmissionBase(BaseModel):
    user_id: str = Field(..., description="ID of the user (Auth0 user ID)")
    model_id: uuid.UUID = Field(..., description="ID of the model")
    challenge_id: uuid.UUID = Field(..., description="ID of the challenge")
    description: Optional[str] = Field(None, description=SUBMISSION_DESCRIPTION)
    dataset_url: Optional[str] = Field(None, description=DATASET_URL_DESCRIPTION)
    status: SubmissionStatus = Field(default=SubmissionStatus.PENDING, description="Status of the submission")
    status_message: Optional[str] = Field(None, description="Status message or error details")

class SubmissionCreate(BaseModel):
    model_id: uuid.UUID = Field(..., description="ID of the model")
    description: Optional[str] = Field(None, description=SUBMISSION_DESCRIPTION)
    dataset_url: Optional[str] = Field(None, description=DATASET_URL_DESCRIPTION)
    # user_id comes from authenticated token

class SubmissionUpdate(BaseModel):
    model_id: Optional[uuid.UUID] = Field(None, description="ID of the model from model table")
    challenge_id: Optional[uuid.UUID] = Field(None, description="ID of the challenge")
    description: Optional[str] = Field(None, description=SUBMISSION_DESCRIPTION)
    dataset_url: Optional[str] = Field(None, description=DATASET_URL_DESCRIPTION)
    # user_id cannot be updated

class SubmissionRead(SubmissionBase):
    id: uuid.UUID = Field(..., description=SUBMISSION_ID_DESCRIPTION)
    created_at: datetime.datetime = Field(..., description="Creation timestamp of the submission")
    updated_at: datetime.datetime = Field(..., description="Last update timestamp of the submission")

    class Config:
        from_attributes = True

class SubmissionCreatedResponse(BaseModel):
    """Response schema for immediate submission creation"""
    id: uuid.UUID = Field(..., description=SUBMISSION_ID_DESCRIPTION)
    status: SubmissionStatus = Field(..., description="Current status of the submission")
    message: str = Field(..., description="Status message")
    
    class Config:
        from_attributes = True

class SubmissionStatusResponse(BaseModel):
    """Response schema for status checking"""
    id: uuid.UUID = Field(..., description=SUBMISSION_ID_DESCRIPTION)
    status: SubmissionStatus = Field(..., description="Current status of the submission")
    status_message: Optional[str] = Field(None, description="Status message or error details")
    progress_percentage: Optional[int] = Field(None, description="Progress percentage (0-100)", ge=0, le=100)
    current_step: Optional[str] = Field(None, description="Current processing step")
    error_details: Optional[str] = Field(None, description="Detailed error information if failed")
    created_at: Optional[datetime.datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime.datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        from_attributes = True
