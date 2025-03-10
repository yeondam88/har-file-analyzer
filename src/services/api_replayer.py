import json
import logging
import time
from typing import Dict, Optional, Tuple, Union

import requests
from sqlalchemy.orm import Session

from src.core.exceptions import APICallNotFoundException, APICallReplayException
from src.models.api_call import APICall
from src.schemas.api_call import APICallReplayRequest, APICallReplayResponse

logger = logging.getLogger(__name__)


class APIReplayer:
    def __init__(self, db: Session):
        self.db = db
    
    def replay_api_call(
        self, call_id: str, replay_request: Optional[APICallReplayRequest] = None
    ) -> APICallReplayResponse:
        """
        Replay an API call from the database.
        
        Args:
            call_id: ID of the API call to replay
            replay_request: Optional customization for the replay
            
        Returns:
            APICallReplayResponse with the replay results
        """
        # Get API call from database
        api_call = self.db.query(APICall).filter(APICall.id == call_id).first()
        if not api_call:
            raise APICallNotFoundException(call_id)
        
        # Default empty replay request if none provided
        if replay_request is None:
            replay_request = APICallReplayRequest()
        
        try:
            # Prepare request
            method, url, headers, body = self._prepare_request(api_call, replay_request)
            
            # Execute request with timing
            status, response_headers, response_body, elapsed_time = self._execute_request(
                method, url, headers, body
            )
            
            # Create response
            return APICallReplayResponse(
                original=api_call,
                replay_status=status,
                replay_headers=response_headers,
                replay_body=response_body,
                replay_time=elapsed_time,
                success=status < 400,  # Consider 4xx and 5xx as errors
            )
        except Exception as e:
            logger.error(f"Error replaying API call {call_id}: {str(e)}")
            raise APICallReplayException(f"Error replaying API call: {str(e)}")
    
    def _prepare_request(
        self, api_call: APICall, replay_request: APICallReplayRequest
    ) -> Tuple[str, str, Dict[str, str], Optional[str]]:
        """
        Prepare the request for replay.
        
        Args:
            api_call: The original API call
            replay_request: Customization for the replay
            
        Returns:
            Tuple of (method, url, headers, body)
        """
        method = api_call.method
        url = api_call.url
        
        # Parse headers
        try:
            headers = json.loads(api_call.headers)
            # Convert from HAR format to requests format
            parsed_headers = {}
            for header in headers:
                name = header.get("name")
                value = header.get("value")
                if name and value:
                    parsed_headers[name] = value
        except (json.JSONDecodeError, TypeError):
            parsed_headers = {}
        
        # Apply custom headers if provided
        if replay_request.custom_headers:
            for name, value in replay_request.custom_headers.items():
                parsed_headers[name] = value
        
        # Set body
        body = api_call.request_body if not replay_request.custom_body else replay_request.custom_body
        
        return method, url, parsed_headers, body
    
    def _execute_request(
        self, method: str, url: str, headers: Dict[str, str], body: Optional[str]
    ) -> Tuple[int, Dict[str, str], str, int]:
        """
        Execute the HTTP request.
        
        Args:
            method: HTTP method
            url: URL to call
            headers: Request headers
            body: Request body
            
        Returns:
            Tuple of (status_code, response_headers, response_body, elapsed_time_ms)
        """
        start_time = time.time()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
                timeout=30,  # 30 seconds timeout
                allow_redirects=True,
            )
            
            # Calculate elapsed time in milliseconds
            elapsed_time = int((time.time() - start_time) * 1000)
            
            # Convert response headers to dict
            response_headers = dict(response.headers)
            
            # Get response body
            try:
                response_body = response.text
            except Exception:
                response_body = "Unable to decode response body"
            
            return response.status_code, response_headers, response_body, elapsed_time
        
        except requests.RequestException as e:
            # Handle request exceptions
            elapsed_time = int((time.time() - start_time) * 1000)
            logger.error(f"Request failed: {str(e)}")
            raise APICallReplayException(f"Request failed: {str(e)}") 