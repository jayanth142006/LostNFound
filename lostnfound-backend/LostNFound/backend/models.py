from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, JSON
from database import Base


class LostItem(Base):
    __tablename__ = "lost_items"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    image_path = Column(String)
    email = Column(String)
    category = Column(String, default="Unknown")
    color = Column(String, default="Unknown")
    location = Column(String, default="Unknown")
    time = Column(String, default="12:00")
    days_since_loss = Column(Integer, default=0)
    created_at = Column(String)
    matched = Column(Integer, default=0) # 0 = false, 1 = true


class FoundItem(Base):
    __tablename__ = "found_items"

    id = Column(Integer, primary_key=True, index=True)
    caption = Column(String)
    image_path = Column(String)
    location = Column(String)
    condition = Column(String)
    created_at = Column(String)
    matched = Column(Integer, default=0)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    lost_item_id = Column(Integer)
    found_item_id = Column(Integer)
    similarity_score = Column(Integer)
    created_at = Column(String)
    verified = Column(Integer, default=0)

class Verification(Base):
    __tablename__ = "verifications"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer)
    confidence_score = Column(Float, default=0.0)
    status = Column(String, default="PENDING") # PENDING, VERIFIED, MANUAL_REVIEW, FAILED
    proof_files = Column(JSON, default=[]) # List of file paths
    questions_json = Column(JSON, default=[]) # Dynamic questions and answers
    attempt_count = Column(Integer, default=0)
    verification_timestamp = Column(String, nullable=True)
    qr_code_path = Column(String, nullable=True)

class DetectiveRequest(BaseModel):
    history: list = []
    userInput: str = ""
    category: str = "Unknown"
    color: str = "Unknown"
    location: str = "Unknown"
    time: str = "12:00"
    days_since_loss: int = 0


class FinalizeRequest(BaseModel):
    history: Optional[List[dict]] = []
