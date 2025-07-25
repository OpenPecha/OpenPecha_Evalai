import uuid
import datetime
from pydantic import BaseModel
from typing import Optional

class ModelBase(BaseModel):
    name: str
    created_by: str
    updated_by: str

class ModelCreate(ModelBase):
    pass

class ModelUpdate(ModelBase):
    name: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

class ModelRead(ModelBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
