from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import datetime
import uuid

class User(Base):
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    firstName = Column(String, nullable=False)
    lastName = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    picture = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    role = Column(String, nullable=True)
