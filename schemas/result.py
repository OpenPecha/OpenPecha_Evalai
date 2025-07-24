import uuid
import datetime
from pydantic import BaseModel
from enum import Enum

class ResultType(str, Enum):
    WER = 'WER'
    CER = 'CER'

class ResultBase(BaseModel):
    type: ResultType
    user_id: uuid.UUID
    submission_id: uuid.UUID
    score: float
    created_by: str
    updated_by: str

class ResultCreate(ResultBase):
    pass

class ResultRead(ResultBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
