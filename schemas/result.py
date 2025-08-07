import uuid
import datetime
from pydantic import BaseModel
from enum import Enum

class ResultType(str, Enum):
    WER = 'WER'
    CER = 'CER'

# basic pydantic for the simple CRUD endpoints
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

# below are for the list of results for the dashboard. nested concepts to send corresponding datas. nested tables are result (submission_id) -> submission (model_id) -> model
class ModelReadNested(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime.datetime
    created_by: str
    updated_at: datetime.datetime
    updated_by: str

    class Config:
        from_attributes = True

class SubmissionReadNested(BaseModel):
    id: uuid.UUID
    user_id: str
    model_id: uuid.UUID
    description: str | None = None
    dataset_url: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model: ModelReadNested

    class Config:
        from_attributes = True

class ResultReadNested(BaseModel):
    id: uuid.UUID
    type: ResultType
    user_id: str
    submission_id: uuid.UUID
    score: float
    created_by: str
    updated_by: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    submission: SubmissionReadNested

    class Config:
        from_attributes = True
