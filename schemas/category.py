import uuid
import datetime
from pydantic import BaseModel
from typing import Optional

class CategoryBase(BaseModel):
    name: str
    created_by: str
    updated_by: str

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    name: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

class CategoryRead(CategoryBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
