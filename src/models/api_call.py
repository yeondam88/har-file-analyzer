import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.db.base import Base


class APICall(Base):
    __tablename__ = "api_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    har_file_id = Column(String(36), ForeignKey("har_files.id"), nullable=False)
    method = Column(String, nullable=False)
    url = Column(String, nullable=False)
    path = Column(String, nullable=False)
    query_string = Column(Text, nullable=True)
    headers = Column(Text, nullable=True)  # Stored as JSON string
    request_body = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_headers = Column(Text, nullable=True)  # Stored as JSON string
    response_body = Column(Text, nullable=True)
    timing_wait = Column(Integer, nullable=True)  # Time waiting for a response (ms)
    timing_receive = Column(Integer, nullable=True)  # Time to receive the response (ms)
    timing_total = Column(Integer, nullable=True)  # Total time for the request (ms)
    is_xhr = Column(Boolean, default=False)  # Whether this is an XHR/fetch request
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    har_file = relationship("HARFile", back_populates="api_calls")
    
    def __repr__(self):
        return f"<APICall {self.method} {self.url}>" 