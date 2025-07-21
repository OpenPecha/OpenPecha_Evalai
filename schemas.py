import datetime
from pydantic import BaseModel
from typing import Optional

# User pydantic schema

class UserBase(BaseModel):
    username: str
    email: str
    picture: Optional[str] = None
    role: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: int
    date_joined: datetime.datetime
    is_active: bool

    class Config:
        from_attributes = True  # for pydantic v2+


# Challenge pydantic schema

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
        # orm_mode = True # pydantic version < 2.*
        from_attribute = True # pydantic version >= 2.*