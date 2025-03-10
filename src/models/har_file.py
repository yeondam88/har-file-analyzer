import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.db.base import Base


class HARFile(Base):
    __tablename__ = "har_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    file_size = Column(Integer, nullable=False)
    browser = Column(String, nullable=True)
    browser_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    description = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", backref="har_files")
    api_calls = relationship("APICall", back_populates="har_file", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HARFile {self.filename}>" 