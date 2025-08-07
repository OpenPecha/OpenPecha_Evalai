import uuid
import datetime
from pydantic import BaseModel
from enum import Enum

class ResultType(str, Enum):
    WER = 'WER'
    CER = 'CER'

class ResultBase(BaseModel):
    type: ResultType
    user_id: str  # Auth0 user ID
    submission_id: uuid.UUID
    score: float
    created_by: str
    updated_by: str

class ResultCreate(BaseModel):
    type: ResultType
    submission_id: uuid.UUID
    score: float
    # user_id, created_by, updated_by come from authenticated token

class ResultRead(ResultBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
