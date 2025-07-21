from pydantic import BaseModel

class ResultBase(BaseModel):
    type: str | None = None
    score: float
    submission_id: int

class ResultCreate(ResultBase):
    pass

class ResultRead(ResultBase):
    id: int
    class Config:
        from_attributes = True
