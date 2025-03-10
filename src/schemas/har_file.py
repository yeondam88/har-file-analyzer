from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class HARFileBase(BaseModel):
    filename: str
    description: Optional[str] = None


class HARFileCreate(HARFileBase):
    pass


class HARFileUpdate(HARFileBase):
    filename: Optional[str] = None


class HARFileInDBBase(HARFileBase):
    id: str
    user_id: str
    file_size: int
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HARFile(HARFileInDBBase):
    pass


class HARFileWithCount(HARFile):
    api_call_count: int 