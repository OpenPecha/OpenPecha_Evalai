import datetime
from pydantic import BaseModel

class ChallengeBase(BaseModel):
    title: str
    image: str | None = None
    dataset: dict
    script: str | None = None
    start_date: datetime.datetime
    end_date: datetime.datetime
    hosted_by: int

class ChallengeCreate(ChallengeBase):
    pass

class ChallengeRead(ChallengeBase):
    id: int
    class Config:
        from_attribute = True
