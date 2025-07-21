import datetime
from pydantic import BaseModel
from typing import Optional

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
        from_attributes = True
