from datetime import datetime
from typing import Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
import json


class APICallBase(BaseModel):
    method: str
    url: str
    path: str
    query_string: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    request_body: Optional[str] = None
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    response_body: Optional[str] = None
    timing_wait: Optional[int] = None
    timing_receive: Optional[int] = None
    timing_total: Optional[int] = None
    is_xhr: Optional[bool] = False
    
    @field_validator('headers', 'response_headers', mode='before')
    @classmethod
    def parse_headers(cls, value):
        if isinstance(value, str):
            try:
                # Parse the JSON string to get the list of header objects
                header_list = json.loads(value)
                # Convert to dictionary format
                result = {}
                for header in header_list:
                    name = header.get("name")
                    value = header.get("value")
                    if name and value:
                        result[name] = value
                return result
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}
        return value
    
    @field_validator('timing_wait', 'timing_receive', 'timing_total', mode='before')
    @classmethod
    def convert_float_to_int(cls, value):
        if isinstance(value, float):
            return int(value)
        return value


class APICallCreate(APICallBase):
    har_file_id: str


class APICallUpdate(BaseModel):
    method: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    query_string: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    request_body: Optional[str] = None
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    response_body: Optional[str] = None
    timing_wait: Optional[int] = None
    timing_receive: Optional[int] = None
    timing_total: Optional[int] = None
    is_xhr: Optional[bool] = None


class APICallInDBBase(APICallBase):
    id: str
    har_file_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APICall(APICallInDBBase):
    pass


class APICallList(BaseModel):
    items: List[APICall]
    total: int


class APICallReplayRequest(BaseModel):
    custom_headers: Optional[Dict[str, str]] = None
    custom_body: Optional[str] = None
    include_credentials: bool = False


class APICallReplayResponse(BaseModel):
    original: APICall
    replay_status: int
    replay_headers: Dict[str, str]
    replay_body: str
    replay_time: int  # in milliseconds
    success: bool 