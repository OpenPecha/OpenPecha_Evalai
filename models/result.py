from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import datetime
import uuid
from enum import Enum

class ResultType(str, Enum):
    WER = 'WER'
    CER = 'CER'

class Result(Base):
    __tablename__ = "result"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    type = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("submission.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    created_by = Column(String, nullable=False) # not needed
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_by = Column(String, nullable=False) # not needed
