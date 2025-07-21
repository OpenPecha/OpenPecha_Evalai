from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, JSON, Integer, Float              
from database import Base
import datetime


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    picture = Column(String)
    role = Column(String)
    date_joined = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    is_active = Column(Boolean, nullable=False, default=True)

class Challenge(Base):
    __tablename__ = "challenge"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    image = Column(String, nullable=True)
    dataset = Column(JSON, nullable=False)
    script = Column(String, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    hosted_by = Column(Integer, ForeignKey("user.id"), index=True)

class Submission(Base):
    __tablename__ = "submission"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenge.id"), index=True)
    submitted_by_id = Column(Integer, ForeignKey("user.id"), index=True)
    dataset = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    submitted_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    input_file = Column(String, nullable=False)

class Result(Base):
    __tablename__ = "result"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=True)
    score = Column(Float, nullable=False)
    submission_id = Column(Integer, ForeignKey("submission.id"), index=True)