import uuid
import datetime
from pydantic import BaseModel

class ModelBase(BaseModel):
    name: str
    created_by: str
    updated_by: str

class ModelCreate(ModelBase):
    pass

class ModelRead(ModelBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True
