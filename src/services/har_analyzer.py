import json
import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from src.models.api_call import APICall
from src.models.har_file import HARFile

logger = logging.getLogger(__name__)


class HARAnalyzer:
    """
    Service for in-depth analysis of HAR files and generating reports.
    Extracts API patterns, authentication methods, common headers, cookies, etc.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_report(self, har_file_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive report for a HAR file.
        
        Args:
            har_file_id: ID of the HAR file to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        # Get HAR file and its API calls
        har_file = self.db.query(HARFile).filter(HARFile.id == har_file_id).first()
        if not har_file:
            raise ValueError(f"HAR file with ID {har_file_id} not found")
        
        api_calls = self.db.query(APICall).filter(APICall.har_file_id == har_file_id).all()
        if not api_calls:
            return {
                "har_file": {
                    "id": har_file.id,
                    "filename": har_file.filename,
                    "file_size": har_file.file_size,
                    "browser": har_file.browser,
                    "browser_version": har_file.browser_version,
                },
                "api_count": 0,
                "message": "No API calls found in this HAR file"
            }
        
        # Perform various analyses
        api_endpoints = self._analyze_api_endpoints(api_calls)
        auth_methods = self._detect_auth_methods(api_calls)
        common_headers = self._analyze_common_headers(api_calls)
        cookies = self._extract_cookies(api_calls)
        response_patterns = self._analyze_response_patterns(api_calls)
        domains = self._extract_domains(api_calls)
        api_groups = self._group_apis_by_path_pattern(api_calls)
        error_patterns = self._analyze_error_patterns(api_calls)
        
        # Compile report
        return {
            "har_file": {
                "id": har_file.id,
                "filename": har_file.filename,
                "file_size": har_file.file_size,
                "browser": har_file.browser,
                "browser_version": har_file.browser_version,
            },
            "summary": {
                "api_count": len(api_calls),
                "domain_count": len(domains),
                "unique_endpoints": len(api_endpoints),
                "auth_methods": list(auth_methods.keys()),
                "has_cookies": bool(cookies),
                "has_error_responses": bool(error_patterns)
            },
            "domains": domains,
            "api_endpoints": api_endpoints,
            "auth_methods": auth_methods,
            "common_headers": common_headers,
            "cookies": cookies,
            "response_patterns": response_patterns,
            "api_groups": api_groups,
            "error_patterns": error_patterns
        }
    
    def _analyze_api_endpoints(self, api_calls: List[APICall]) -> List[Dict[str, Any]]:
        """
        Analyze API endpoints, their usage patterns, and parameters.
        """
        endpoints = {}
        
        for call in api_calls:
            # Create a unique key for this endpoint (method + path)
            key = f"{call.method}:{call.path}"
            
            if key not in endpoints:
                # Parse query parameters
                query_params = {}
                if call.query_string:
                    try:
                        query_params = {k: v[0] if len(v) == 1 else v 
                                       for k, v in parse_qs(call.query_string).items()}
                    except Exception as e:
                        logger.warning(f"Error parsing query string: {str(e)}")
                
                # Parse request body if it exists
                body_params = {}
                if call.request_body:
                    try:
                        # Try to parse as JSON
                        body_params = json.loads(call.request_body)
                    except json.JSONDecodeError:
                        # If not JSON, try to parse as form data
                        try:
                            body_params = {k: v[0] if len(v) == 1 else v 
                                          for k, v in parse_qs(call.request_body).items()}
                        except Exception:
                            # If not form data, store as raw string
                            body_params = {"raw": call.request_body[:100] + "..." if len(call.request_body) > 100 else call.request_body}
                
                # Parse headers
                headers = {}
                if call.headers:
                    try:
                        headers_data = json.loads(call.headers)
                        for header in headers_data:
                            name = header.get("name")
                            value = header.get("value")
                            if name and value:
                                headers[name] = value
                    except Exception as e:
                        logger.warning(f"Error parsing headers: {str(e)}")
                
                # Store endpoint info
                endpoints[key] = {
                    "method": call.method,
                    "path": call.path,
                    "url": call.url,
                    "query_params": query_params,
                    "body_params": body_params,
                    "headers": headers,
                    "count": 1,
                    "response_codes": [call.response_status] if call.response_status else [],
                    "is_xhr": call.is_xhr
                }
            else:
                # Update existing endpoint data
                endpoints[key]["count"] += 1
                if call.response_status and call.response_status not in endpoints[key]["response_codes"]:
                    endpoints[key]["response_codes"].append(call.response_status)
        
        # Convert to list and sort by count (most frequent first)
        return [v for k, v in sorted(endpoints.items(), key=lambda x: x[1]["count"], reverse=True)]
    
    def _detect_auth_methods(self, api_calls: List[APICall]) -> Dict[str, Any]:
        """
        Detect authentication methods used in the API calls.
        """
        auth_methods = {}
        
        # Check for common auth patterns
        for call in api_calls:
            headers = {}
            if call.headers:
                try:
                    headers_data = json.loads(call.headers)
                    for header in headers_data:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        headers[name] = value
                except Exception:
                    continue
            
            # Check for Authorization header
            if "authorization" in headers:
                auth_value = headers["authorization"]
                
                # Check for Bearer token
                if auth_value.startswith("Bearer "):
                    if "bearer_token" not in auth_methods:
                        auth_methods["bearer_token"] = {
                            "description": "Bearer token authentication",
                            "header": "Authorization: Bearer [token]",
                            "examples": [auth_value[:30] + "..." if len(auth_value) > 30 else auth_value],
                            "endpoints": [call.path]
                        }
                    elif call.path not in auth_methods["bearer_token"]["endpoints"]:
                        auth_methods["bearer_token"]["endpoints"].append(call.path)
                
                # Check for Basic auth
                elif auth_value.startswith("Basic "):
                    if "basic_auth" not in auth_methods:
                        auth_methods["basic_auth"] = {
                            "description": "Basic authentication (username:password)",
                            "header": "Authorization: Basic [base64-encoded-credentials]",
                            "examples": [auth_value[:30] + "..." if len(auth_value) > 30 else auth_value],
                            "endpoints": [call.path]
                        }
                    elif call.path not in auth_methods["basic_auth"]["endpoints"]:
                        auth_methods["basic_auth"]["endpoints"].append(call.path)
                
                # Other Authorization header types
                else:
                    auth_type = auth_value.split(" ")[0].lower() if " " in auth_value else "custom"
                    if auth_type not in auth_methods:
                        auth_methods[auth_type] = {
                            "description": f"{auth_type.capitalize()} authentication",
                            "header": f"Authorization: {auth_value[:30]}...",
                            "examples": [auth_value[:30] + "..." if len(auth_value) > 30 else auth_value],
                            "endpoints": [call.path]
                        }
                    elif call.path not in auth_methods[auth_type]["endpoints"]:
                        auth_methods[auth_type]["endpoints"].append(call.path)
            
            # Check for API key in query parameters
            if call.query_string:
                query_params = parse_qs(call.query_string)
                for param in ["api_key", "apikey", "key", "token", "access_token"]:
                    if param in query_params:
                        if "api_key_query" not in auth_methods:
                            auth_methods["api_key_query"] = {
                                "description": "API key authentication in query parameter",
                                "parameter": param,
                                "examples": [query_params[param][0][:15] + "..." if len(query_params[param][0]) > 15 else query_params[param][0]],
                                "endpoints": [call.path]
                            }
                        elif call.path not in auth_methods["api_key_query"]["endpoints"]:
                            auth_methods["api_key_query"]["endpoints"].append(call.path)
            
            # Check for API key in headers
            for header_name in ["x-api-key", "api-key", "x-access-token", "x-token"]:
                if header_name in headers:
                    if "api_key_header" not in auth_methods:
                        auth_methods["api_key_header"] = {
                            "description": "API key authentication in custom header",
                            "header": f"{header_name}: [key]",
                            "examples": [headers[header_name][:15] + "..." if len(headers[header_name]) > 15 else headers[header_name]],
                            "endpoints": [call.path]
                        }
                    elif call.path not in auth_methods["api_key_header"]["endpoints"]:
                        auth_methods["api_key_header"]["endpoints"].append(call.path)
            
            # Check for cookie-based authentication
            if "cookie" in headers:
                cookie_str = headers["cookie"]
                cookies = {}
                
                # Parse cookies
                for cookie_pair in cookie_str.split(";"):
                    if "=" in cookie_pair:
                        name, value = cookie_pair.strip().split("=", 1)
                        cookies[name.strip()] = value.strip()
                
                # Check for common auth cookie names
                for cookie_name in ["session", "sessionid", "token", "auth", "jwt", "access_token"]:
                    if cookie_name in cookies:
                        if "cookie_auth" not in auth_methods:
                            auth_methods["cookie_auth"] = {
                                "description": "Cookie-based authentication",
                                "cookie_name": cookie_name,
                                "examples": [cookies[cookie_name][:15] + "..." if len(cookies[cookie_name]) > 15 else cookies[cookie_name]],
                                "endpoints": [call.path]
                            }
                        elif call.path not in auth_methods["cookie_auth"]["endpoints"]:
                            auth_methods["cookie_auth"]["endpoints"].append(call.path)
        
        return auth_methods
    
    def _analyze_common_headers(self, api_calls: List[APICall]) -> Dict[str, Any]:
        """
        Analyze common headers used in API calls.
        """
        # Count header occurrences
        header_counts = defaultdict(int)
        header_values = defaultdict(set)
        
        for call in api_calls:
            if call.headers:
                try:
                    headers_data = json.loads(call.headers)
                    for header in headers_data:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        if name and value:
                            header_counts[name] += 1
                            # Store a sample of values (limit to 3 per header)
                            if len(header_values[name]) < 3:
                                header_values[name].add(value[:50] + "..." if len(value) > 50 else value)
                except Exception as e:
                    logger.warning(f"Error parsing headers: {str(e)}")
        
        # Calculate percentage of calls that include each header
        total_calls = len(api_calls)
        header_stats = {}
        
        for header, count in header_counts.items():
            percentage = (count / total_calls) * 100
            header_stats[header] = {
                "count": count,
                "percentage": round(percentage, 2),
                "sample_values": list(header_values[header])
            }
        
        # Sort by frequency (most common first)
        return {k: v for k, v in sorted(header_stats.items(), key=lambda x: x[1]["count"], reverse=True)}
    
    def _extract_cookies(self, api_calls: List[APICall]) -> Dict[str, Any]:
        """
        Extract and analyze cookies from API calls.
        """
        cookies = {}
        
        for call in api_calls:
            if call.headers:
                try:
                    headers_data = json.loads(call.headers)
                    for header in headers_data:
                        name = header.get("name", "").lower()
                        value = header.get("value", "")
                        
                        if name == "cookie" and value:
                            # Parse cookie string
                            for cookie_pair in value.split(";"):
                                if "=" in cookie_pair:
                                    cookie_name, cookie_value = cookie_pair.strip().split("=", 1)
                                    cookie_name = cookie_name.strip()
                                    cookie_value = cookie_value.strip()
                                    
                                    if cookie_name not in cookies:
                                        cookies[cookie_name] = {
                                            "example_value": cookie_value[:20] + "..." if len(cookie_value) > 20 else cookie_value,
                                            "count": 1,
                                            "endpoints": [call.path]
                                        }
                                    else:
                                        cookies[cookie_name]["count"] += 1
                                        if call.path not in cookies[cookie_name]["endpoints"]:
                                            cookies[cookie_name]["endpoints"].append(call.path)
                        
                        elif name == "set-cookie" and value:
                            # Extract cookie name from Set-Cookie header
                            if "=" in value:
                                cookie_parts = value.split(";")
                                main_part = cookie_parts[0]
                                cookie_name, cookie_value = main_part.split("=", 1)
                                cookie_name = cookie_name.strip()
                                cookie_value = cookie_value.strip()
                                
                                # Extract additional cookie attributes
                                attributes = {}
                                for part in cookie_parts[1:]:
                                    part = part.strip()
                                    if "=" in part:
                                        attr_name, attr_value = part.split("=", 1)
                                        attributes[attr_name.strip().lower()] = attr_value.strip()
                                    else:
                                        attributes[part.lower()] = True
                                
                                if cookie_name not in cookies:
                                    cookies[cookie_name] = {
                                        "example_value": cookie_value[:20] + "..." if len(cookie_value) > 20 else cookie_value,
                                        "count": 1,
                                        "endpoints": [call.path],
                                        "attributes": attributes
                                    }
                                else:
                                    cookies[cookie_name]["count"] += 1
                                    if call.path not in cookies[cookie_name]["endpoints"]:
                                        cookies[cookie_name]["endpoints"].append(call.path)
                                    if "attributes" not in cookies[cookie_name]:
                                        cookies[cookie_name]["attributes"] = attributes
                except Exception as e:
                    logger.warning(f"Error extracting cookies: {str(e)}")
        
        # Sort by count (most common first)
        return {k: v for k, v in sorted(cookies.items(), key=lambda x: x[1]["count"], reverse=True)}
    
    def _analyze_response_patterns(self, api_calls: List[APICall]) -> Dict[str, Any]:
        """
        Analyze response patterns and structures.
        """
        response_types = defaultdict(int)
        response_sizes = []
        response_time_avg = 0
        response_time_count = 0
        status_codes = defaultdict(int)
        content_types = defaultdict(int)
        json_structures = {}
        
        for call in api_calls:
            # Count status codes
            if call.response_status:
                status_codes[call.response_status] += 1
            
            # Extract content type
            content_type = "unknown"
            if call.response_headers:
                try:
                    headers_data = json.loads(call.response_headers)
                    for header in headers_data:
                        if header.get("name", "").lower() == "content-type":
                            content_type = header.get("value", "unknown")
                            content_types[content_type] += 1
                            break
                except Exception:
                    pass
            
            # Calculate average response time
            if call.timing_total and call.timing_total > 0:
                response_time_avg += call.timing_total
                response_time_count += 1
            
            # Analyze response sizes
            if call.response_body:
                size = len(call.response_body)
                response_sizes.append(size)
                
                # Determine response type
                if content_type.startswith("application/json"):
                    response_types["json"] += 1
                    
                    # Analyze JSON structure for common patterns
                    try:
                        json_data = json.loads(call.response_body)
                        
                        # Extract top-level keys for structure analysis
                        if isinstance(json_data, dict):
                            structure_key = ",".join(sorted(json_data.keys()))
                            if len(structure_key) < 100:  # Don't analyze extremely complex structures
                                if structure_key not in json_structures:
                                    json_structures[structure_key] = {
                                        "keys": sorted(json_data.keys()),
                                        "count": 1,
                                        "example_endpoint": call.path
                                    }
                                else:
                                    json_structures[structure_key]["count"] += 1
                    except json.JSONDecodeError:
                        pass
                elif content_type.startswith("text/html"):
                    response_types["html"] += 1
                elif content_type.startswith("text/plain"):
                    response_types["text"] += 1
                elif content_type.startswith("application/xml") or content_type.startswith("text/xml"):
                    response_types["xml"] += 1
                else:
                    response_types["other"] += 1
        
        # Calculate average response time
        avg_time = response_time_avg / response_time_count if response_time_count > 0 else 0
        
        # Calculate response size statistics
        if response_sizes:
            avg_size = sum(response_sizes) / len(response_sizes)
            min_size = min(response_sizes)
            max_size = max(response_sizes)
        else:
            avg_size = min_size = max_size = 0
        
        # Sort JSON structures by frequency
        sorted_structures = {k: v for k, v in sorted(json_structures.items(), key=lambda x: x[1]["count"], reverse=True)}
        
        return {
            "status_codes": {k: v for k, v in sorted(status_codes.items(), key=lambda x: x[0])},
            "content_types": dict(content_types),
            "response_types": dict(response_types),
            "response_sizes": {
                "average": round(avg_size),
                "min": min_size,
                "max": max_size
            },
            "response_time": {
                "average_ms": round(avg_time)
            },
            "json_structures": sorted_structures
        }
    
    def _extract_domains(self, api_calls: List[APICall]) -> Dict[str, Dict[str, Any]]:
        """
        Extract and analyze domains from API calls.
        """
        domains = {}
        
        for call in api_calls:
            url = call.url
            if url:
                try:
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc
                    
                    if domain not in domains:
                        domains[domain] = {
                            "count": 1,
                            "methods": [call.method],
                            "paths": [call.path]
                        }
                    else:
                        domains[domain]["count"] += 1
                        if call.method not in domains[domain]["methods"]:
                            domains[domain]["methods"].append(call.method)
                        if call.path not in domains[domain]["paths"]:
                            domains[domain]["paths"].append(call.path)
                except Exception:
                    continue
        
        # Sort by count (most frequent first)
        return {k: v for k, v in sorted(domains.items(), key=lambda x: x[1]["count"], reverse=True)}
    
    def _group_apis_by_path_pattern(self, api_calls: List[APICall]) -> Dict[str, Dict[str, Any]]:
        """
        Group APIs by common path patterns to identify resource groups.
        """
        # Identify common path prefixes
        path_groups = defaultdict(list)
        
        for call in api_calls:
            path = call.path
            parts = path.strip('/').split('/')
            
            # Group by first path segment if available
            if parts and parts[0]:
                group_key = f"/{parts[0]}"
                path_groups[group_key].append(call)
        
        # For each group, analyze the patterns
        result = {}
        for group_key, calls in path_groups.items():
            # Count methods
            methods = defaultdict(int)
            for call in calls:
                methods[call.method] += 1
            
            # Extract unique paths
            unique_paths = set()
            for call in calls:
                unique_paths.add(call.path)
            
            # Try to identify REST patterns
            rest_patterns = self._identify_rest_patterns(unique_paths)
            
            result[group_key] = {
                "count": len(calls),
                "methods": dict(methods),
                "unique_paths": len(unique_paths),
                "examples": list(sorted(unique_paths))[:5],  # Show up to 5 examples
                "rest_patterns": rest_patterns
            }
        
        # Sort by frequency
        return {k: v for k, v in sorted(result.items(), key=lambda x: x[1]["count"], reverse=True)}
    
    def _identify_rest_patterns(self, paths: Set[str]) -> List[Dict[str, Any]]:
        """
        Identify REST API patterns from a set of paths.
        """
        patterns = []
        path_ids = {}
        
        # Common patterns for identifiers in paths
        id_patterns = [
            r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',  # UUID
            r'/([0-9a-f]{24})',  # MongoDB ObjectId
            r'/(\d+)',  # Numeric ID
        ]
        
        # Group similar paths
        for path in paths:
            path_parts = path.strip('/').split('/')
            
            # Reconstruct path with placeholders for IDs
            normalized_path = []
            for i, part in enumerate(path_parts):
                # Check if this part matches any ID pattern
                is_id = False
                for pattern in id_patterns:
                    if re.match(pattern, f"/{part}"):
                        normalized_path.append("{id}")
                        is_id = True
                        break
                
                if not is_id:
                    normalized_path.append(part)
            
            normalized_str = '/' + '/'.join(normalized_path)
            
            if normalized_str not in path_ids:
                path_ids[normalized_str] = {
                    "pattern": normalized_str,
                    "examples": [path],
                    "count": 1
                }
            else:
                path_ids[normalized_str]["count"] += 1
                if len(path_ids[normalized_str]["examples"]) < 3:  # Store up to 3 examples
                    path_ids[normalized_str]["examples"].append(path)
        
        # Convert to list and sort by count
        patterns = [v for k, v in sorted(path_ids.items(), key=lambda x: x[1]["count"], reverse=True)]
        
        return patterns
    
    def _analyze_error_patterns(self, api_calls: List[APICall]) -> Dict[str, Any]:
        """
        Analyze error response patterns.
        """
        error_patterns = {}
        
        for call in api_calls:
            # Check for error status codes (4xx, 5xx)
            if call.response_status and 400 <= call.response_status < 600:
                status = call.response_status
                
                # Try to parse response body as JSON to extract error details
                error_structure = {}
                if call.response_body:
                    try:
                        data = json.loads(call.response_body)
                        if isinstance(data, dict):
                            # Look for common error keys
                            for key in ["error", "errors", "message", "detail", "details", "code"]:
                                if key in data:
                                    error_structure[key] = data[key]
                    except json.JSONDecodeError:
                        # Not JSON, store a snippet
                        error_structure["raw"] = call.response_body[:100] + "..." if len(call.response_body) > 100 else call.response_body
                
                # Group by status code
                if status not in error_patterns:
                    error_patterns[status] = {
                        "count": 1,
                        "examples": [{
                            "path": call.path,
                            "method": call.method,
                            "structure": error_structure
                        }]
                    }
                else:
                    error_patterns[status]["count"] += 1
                    if len(error_patterns[status]["examples"]) < 3:  # Store up to 3 examples per status
                        error_patterns[status]["examples"].append({
                            "path": call.path,
                            "method": call.method,
                            "structure": error_structure
                        })
        
        return error_patterns
    
    def analyze_auth(self, har_file_id: str) -> Dict[str, Any]:
        """
        Analyze authentication methods and patterns in the HAR file.
        
        Args:
            har_file_id: ID of the HAR file to analyze
            
        Returns:
            Dictionary containing auth analysis results
        """
        # Get the general report first
        report = self.generate_report(har_file_id)
        
        # Extract only the auth-related sections
        auth_report = {
            "har_file": report["har_file"],
            "api_count": report.get("api_count", 0),  # Use get with default value
            "auth_methods": report.get("auth_methods", {}),
            "cookies": report.get("cookies", {}),
            "security_headers": self._analyze_security_headers(har_file_id),
            "auth_flows": self._detect_auth_flows(har_file_id)
        }
        
        return auth_report
    
    def _analyze_security_headers(self, har_file_id: str) -> Dict[str, Any]:
        """Analyze security-related headers in the API calls"""
        security_headers = {
            "content_security_policy": [],
            "strict_transport_security": [],
            "x_content_type_options": [],
            "x_frame_options": [],
            "x_xss_protection": []
        }
        
        api_calls = self.db.query(APICall).filter(APICall.har_file_id == har_file_id).all()
        
        for call in api_calls:
            response_headers = json.loads(call.response_headers) if call.response_headers else {}
            
            # Check for security headers
            if "Content-Security-Policy" in response_headers:
                security_headers["content_security_policy"].append({
                    "url": call.url,
                    "policy": response_headers["Content-Security-Policy"]
                })
                
            if "Strict-Transport-Security" in response_headers:
                security_headers["strict_transport_security"].append({
                    "url": call.url,
                    "policy": response_headers["Strict-Transport-Security"]
                })
                
            if "X-Content-Type-Options" in response_headers:
                security_headers["x_content_type_options"].append({
                    "url": call.url,
                    "value": response_headers["X-Content-Type-Options"]
                })
                
            if "X-Frame-Options" in response_headers:
                security_headers["x_frame_options"].append({
                    "url": call.url,
                    "value": response_headers["X-Frame-Options"]
                })
                
            if "X-XSS-Protection" in response_headers:
                security_headers["x_xss_protection"].append({
                    "url": call.url,
                    "value": response_headers["X-XSS-Protection"]
                })
        
        return security_headers
    
    def _detect_auth_flows(self, har_file_id: str) -> Dict[str, Any]:
        """Detect authentication flows in the sequence of API calls"""
        flows = {
            "potential_login_endpoints": [],
            "potential_logout_endpoints": [],
            "token_refresh_endpoints": []
        }
        
        api_calls = self.db.query(APICall).filter(APICall.har_file_id == har_file_id).all()
        
        # Sort by timestamp if available, otherwise use id
        try:
            api_calls.sort(key=lambda x: x.timestamp if hasattr(x, 'timestamp') else x.id)
        except Exception:
            # If sorting fails, just use the order they're in
            pass
        
        for i, call in enumerate(api_calls):
            url_path = urlparse(call.url).path.lower()
            
            # Detect login endpoints
            if (call.method == "POST" and 
                any(term in url_path for term in ["/login", "/signin", "/auth", "/token"])):
                flows["potential_login_endpoints"].append({
                    "url": call.url,
                    "method": call.method,
                    "status_code": call.status_code
                })
            
            # Detect logout endpoints
            if (any(term in url_path for term in ["/logout", "/signout"]) or
                (call.request_body and "logout" in call.request_body.lower())):
                flows["potential_logout_endpoints"].append({
                    "url": call.url,
                    "method": call.method,
                    "status_code": call.status_code
                })
            
            # Detect token refresh
            if ((call.method == "POST" and 
                any(term in url_path for term in ["/refresh", "/token"])) or
                (call.request_body and "refresh_token" in call.request_body.lower())):
                flows["token_refresh_endpoints"].append({
                    "url": call.url,
                    "method": call.method,
                    "status_code": call.status_code
                })
        
        return flows
    
    def analyze_endpoints(self, har_file_id: str) -> Dict[str, Any]:
        """
        Analyze API endpoints in the HAR file.
        
        Args:
            har_file_id: ID of the HAR file to analyze
            
        Returns:
            Dictionary containing endpoints analysis results
        """
        # Get the general report first
        report = self.generate_report(har_file_id)
        
        # Extract only the endpoint-related sections
        endpoints_report = {
            "har_file": report["har_file"],
            "api_count": report.get("api_count", 0),
            "unique_endpoints": report.get("unique_endpoints", []),
            "http_methods": report.get("http_methods", {}),
            "endpoint_details": self._analyze_endpoint_details(har_file_id)
        }
        
        return endpoints_report
    
    def _analyze_endpoint_details(self, har_file_id: str) -> Dict[str, Any]:
        """Analyze details of each unique endpoint"""
        endpoint_details = {}
        
        # Get API calls
        api_calls = self.db.query(APICall).filter(APICall.har_file_id == har_file_id).all()
        
        # Group by endpoint path
        endpoints = {}
        for call in api_calls:
            url_parts = urlparse(call.url)
            path = url_parts.path
            
            if path not in endpoints:
                endpoints[path] = []
            
            endpoints[path].append(call)
        
        # Analyze each endpoint
        for path, calls in endpoints.items():
            methods = set(call.method for call in calls)
            
            # Safely get status codes
            status_codes = set()
            for call in calls:
                try:
                    if hasattr(call, 'status_code'):
                        status_codes.add(call.status_code)
                    elif hasattr(call, 'data'):
                        # Try to get status code from data JSON
                        data = json.loads(call.data)
                        if 'status' in data:
                            status_codes.add(data['status'])
                except Exception:
                    pass
            
            # Analyze query parameters
            query_params = set()
            for call in calls:
                url_parts = urlparse(call.url)
                if url_parts.query:
                    params = parse_qs(url_parts.query)
                    query_params.update(params.keys())
            
            # Analyze request bodies
            request_body_types = set()
            for call in calls:
                if hasattr(call, 'request_body') and call.request_body:
                    try:
                        # Try to parse as JSON
                        json.loads(call.request_body)
                        request_body_types.add("application/json")
                    except json.JSONDecodeError:
                        # If not JSON, check if it's form data
                        if "=" in call.request_body and "&" in call.request_body:
                            request_body_types.add("application/x-www-form-urlencoded")
                        else:
                            request_body_types.add("text/plain")
            
            # Analyze response content types
            response_types = set()
            for call in calls:
                if hasattr(call, 'response_headers') and call.response_headers:
                    response_headers = json.loads(call.response_headers)
                    if "Content-Type" in response_headers:
                        content_type = response_headers["Content-Type"].split(";")[0]
                        response_types.add(content_type)
            
            # Store details for this endpoint
            endpoint_details[path] = {
                "methods": list(methods),
                "status_codes": list(status_codes),
                "query_parameters": list(query_params),
                "request_body_types": list(request_body_types),
                "response_content_types": list(response_types),
                "call_count": len(calls)
            }
        
        return endpoint_details 