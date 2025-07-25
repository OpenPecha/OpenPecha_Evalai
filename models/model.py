from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import datetime
import uuid

class Model(Base):
    """
    This refers to a specific ML model name that user will select before submission e.g. Google Vision OCR, OpenAI Whisper.
    
    """ 
    __tablename__ = "model"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    created_by = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_by = Column(String, nullable=False)