from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import datetime
import uuid
import enum

class SubmissionStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Submission(Base):
    __tablename__ = "submission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False, index=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("model.id"), nullable=False, index=True)
    challenge_id = Column(UUID(as_uuid=True), ForeignKey("challenge.id"), nullable=False, index=True)
    description = Column(String, nullable=True)
    dataset_url = Column(String, nullable=True)
    status = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.PENDING)
    status_message = Column(String, nullable=True)  # For error messages or progress info
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
