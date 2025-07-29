import uuid
import datetime
from pydantic import BaseModel, Field
from typing import Optional

class UserBase(BaseModel):
    firstName: str = Field(..., description="First name of the user")
    lastName: str = Field(..., description="Last name of the user")
    email: str = Field(..., description="Email of the user")
    picture: Optional[str] = Field(None, description="Profile picture url (optional)")
    role: Optional[str] = Field(None, description="Role of the user (optional)")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    firstName: Optional[str] = Field(None, description="First name of the user")
    lastName: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(None, description="Email of the user")
    picture: Optional[str] = Field(None, description="Profile picture url (optional)")
    role: Optional[str] = Field(None, description="Role of the user (optional)")

class UserRead(UserBase):
    id: uuid.UUID = Field(..., description="ID of the user")
    created_at: datetime.datetime = Field(..., description="Creation timestamp of the user")
    updated_at: datetime.datetime = Field(..., description="Last update timestamp of the user")

    class Config:
        from_attributes = True
