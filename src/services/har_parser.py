import json
import logging
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from src.core.exceptions import InvalidHARFileException, HARFileProcessingException
from src.models.api_call import APICall
from src.models.har_file import HARFile
from src.schemas.api_call import APICallCreate

logger = logging.getLogger(__name__)


class HARParser:
    def __init__(self, db: Session):
        self.db = db

    def parse_har_file(self, content: bytes, filename: str, user_id: str) -> Tuple[HARFile, List[APICall]]:
        """
        Parse a HAR file and extract API calls.
        
        Args:
            content: HAR file content as bytes
            filename: Name of the HAR file
            user_id: ID of the user who uploaded the HAR file
            
        Returns:
            A tuple containing the HARFile model instance and a list of APICall model instances
        """
        try:
            # Parse HAR content
            har_data = json.loads(content.decode("utf-8"))
            
            # Check if it's a valid HAR file
            if "log" not in har_data or "entries" not in har_data["log"]:
                raise InvalidHARFileException("Invalid HAR file format: missing 'log' or 'entries'")
            
            # Extract browser info
            browser, browser_version = self._extract_browser_info(har_data)
            
            # Create HAR file record
            har_file = HARFile(
                filename=filename,
                user_id=user_id,
                file_size=len(content),
                browser=browser,
                browser_version=browser_version,
            )
            self.db.add(har_file)
            self.db.flush()  # Get the ID without committing
            
            # Process entries (API calls)
            api_calls = self._process_entries(har_data["log"]["entries"], har_file.id)
            
            # Add all API calls to the database
            for api_call in api_calls:
                self.db.add(api_call)
            
            # Commit the transaction
            self.db.commit()
            return har_file, api_calls
            
        except json.JSONDecodeError as e:
            raise InvalidHARFileException(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            # Rollback in case of any error
            self.db.rollback()
            logger.error(f"Error processing HAR file: {str(e)}")
            raise HARFileProcessingException(str(e))

    def _extract_browser_info(self, har_data: Dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract browser information from HAR data.
        
        Args:
            har_data: Parsed HAR file data
            
        Returns:
            A tuple containing the browser name and version
        """
        browser = None
        browser_version = None
        
        try:
            creator = har_data.get("log", {}).get("creator", {})
            browser = creator.get("name")
            browser_version = creator.get("version")
        except Exception as e:
            logger.warning(f"Failed to extract browser info: {str(e)}")
        
        return browser, browser_version

    def _process_entries(self, entries: List[Dict], har_file_id: str) -> List[APICall]:
        """
        Process HAR entries and convert them to APICall objects.
        
        Args:
            entries: List of HAR entries (API calls)
            har_file_id: ID of the HARFile record
            
        Returns:
            List of APICall objects ready to be saved to the database
        """
        api_calls = []
        
        for entry in entries:
            try:
                # Extract request and response
                request = entry.get("request", {})
                response = entry.get("response", {})
                
                # Parse URL
                url = request.get("url", "")
                parsed_url = urlparse(url)
                path = parsed_url.path
                query_string = parsed_url.query
                
                # Extract timings
                timings = entry.get("timings", {})
                
                # Create API call
                api_call = APICall(
                    har_file_id=har_file_id,
                    method=request.get("method", ""),
                    url=url,
                    path=path,
                    query_string=query_string,
                    headers=json.dumps(request.get("headers", [])),
                    request_body=self._extract_request_body(request),
                    response_status=response.get("status", 0),
                    response_headers=json.dumps(response.get("headers", [])),
                    response_body=self._extract_response_body(response),
                    timing_wait=timings.get("wait", 0),
                    timing_receive=timings.get("receive", 0),
                    timing_total=sum(v for k, v in timings.items() if isinstance(v, (int, float)) and v >= 0),
                    is_xhr=self._is_xhr_request(request),
                )
                api_calls.append(api_call)
            except Exception as e:
                # Log error and continue with the next entry
                logger.warning(f"Error processing entry: {str(e)}")
        
        return api_calls

    def _extract_request_body(self, request: Dict) -> Optional[str]:
        """
        Extract request body from the request data.
        
        Args:
            request: HAR request object
            
        Returns:
            Request body as a string or None if no body
        """
        try:
            post_data = request.get("postData", {})
            if "text" in post_data:
                return post_data.get("text", "")
            elif "params" in post_data:
                # Handle form data
                params = post_data.get("params", [])
                return json.dumps({p.get("name"): p.get("value") for p in params})
            return None
        except Exception as e:
            logger.warning(f"Error extracting request body: {str(e)}")
            return None

    def _extract_response_body(self, response: Dict) -> Optional[str]:
        """
        Extract response body from the response data.
        
        Args:
            response: HAR response object
            
        Returns:
            Response body as a string or None if no body
        """
        try:
            content = response.get("content", {})
            if "text" in content:
                return content.get("text", "")
            return None
        except Exception as e:
            logger.warning(f"Error extracting response body: {str(e)}")
            return None

    def _is_xhr_request(self, request: Dict) -> bool:
        """
        Determine if a request is an XHR/fetch request.
        
        Args:
            request: HAR request object
            
        Returns:
            True if the request is an XHR/fetch request, False otherwise
        """
        # Check headers for XHR indicators
        headers = request.get("headers", [])
        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "").lower()
            
            # Common XHR/fetch indicators
            if name == "x-requested-with" and "xmlhttprequest" in value:
                return True
            if name == "accept" and "application/json" in value:
                return True
        return False 