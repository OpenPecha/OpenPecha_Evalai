import datetime
from pydantic import BaseModel

class SubmissionBase(BaseModel):
    challenge_id: int
    submitted_by_id: int
    dataset: dict | None = None
    results: dict | None = None
    input_file: str

class SubmissionCreate(SubmissionBase):
    pass

class SubmissionRead(SubmissionBase):
    id: int
    submitted_at: datetime.datetime
    class Config:
        from_attributes = True
