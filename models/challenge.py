from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from database import Base
import datetime
import uuid
from sqlalchemy.orm import relationship

class Challenge(Base):
    """
    This table refers to a specific challenge Card which will be layed out on frontend.
    e.g name of cards - Tibetan OCR, Tibetan STT, Tibetan ASR, Tibetan TTS, Tibetan MT etc.
    """
    __tablename__ = "challenge"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    title = Column(String, nullable=False)
    image_uri = Column(String, nullable=True)
    # this image_uri is an optional field but we must send the image so that challenge can have its corresponding image in the frontend.
    category_id = Column(UUID(as_uuid=True), ForeignKey("category.id"), nullable=False, index=True)
    # this category_id is a foreign key to the category table. it basically is a reference to the category that the challenge belongs to. eg. STT, ASR, TTS, OCR. we will have to retrieve the category name from the category table using this id
    created_by = Column(String, ForeignKey("user.id"), nullable=False, index=True)
    # this created_by is a foreign key to the user table. it basically is a reference to the user that created the challenge
    ground_truth = Column(String, nullable=False)  # URL to ground truth JSON file
    # this ground_truth is a URL to the ground truth JSON file. it is a required field. the url is been thought to be stored in s3.
    description = Column(String, nullable=True)
    # this description is an optional field but i might chane it later. as a description is must to explain what the challenge is about.
    status = Column(String, nullable=True)
    # this status is an optional field but i might chane it later. as a status is must to explain what the challenge is about.
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Relationship to Category
    category = relationship("Category", back_populates="challenges")
