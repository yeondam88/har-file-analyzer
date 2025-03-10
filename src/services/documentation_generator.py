import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from src.models.har_file import HARFile

logger = logging.getLogger(__name__)


class DocumentationGenerator:
    """
    Service for generating API documentation in markdown format 
    based on HAR file analysis reports.
    """
    
    @staticmethod
    def generate_markdown(har_file: HARFile, analysis_report: Dict[str, Any]) -> str:
        """
        Generate markdown documentation from HAR file analysis.
        
        Args:
            har_file: The HAR file model
            analysis_report: The analysis report from HARAnalyzer
            
        Returns:
            Markdown string
        """
        # Begin building the markdown document
        markdown = []
        
        # Add header and metadata
        markdown.append(f"# API Documentation - {har_file.filename}")
        markdown.append("")
        markdown.append(f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        markdown.append("")
        
        # Add file metadata
        markdown.append("## File Information")
        markdown.append("")
        markdown.append(f"- **Filename**: {har_file.filename}")
        if har_file.description:
            markdown.append(f"- **Description**: {har_file.description}")
        markdown.append(f"- **Size**: {DocumentationGenerator._format_file_size(har_file.file_size)}")
        if har_file.browser:
            markdown.append(f"- **Browser**: {har_file.browser} {har_file.browser_version or ''}")
        markdown.append(f"- **Captured on**: {har_file.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        markdown.append("")
        
        # Add summary
        markdown.append("## Summary")
        markdown.append("")
        summary = analysis_report.get("summary", {})
        markdown.append(f"- **Total API Calls**: {summary.get('api_count', 0)}")
        markdown.append(f"- **Unique Endpoints**: {summary.get('unique_endpoints', 0)}")
        markdown.append(f"- **Domains**: {summary.get('domain_count', 0)}")
        
        # Add authentication methods if present
        auth_methods = summary.get("auth_methods", [])
        if auth_methods:
            markdown.append(f"- **Authentication Methods**: {', '.join(auth_methods)}")
        markdown.append("")
        
        # Add domains section
        markdown.append("## Domains")
        markdown.append("")
        domains = analysis_report.get("domains", {})
        for domain, domain_info in domains.items():
            markdown.append(f"### {domain}")
            markdown.append("")
            markdown.append(f"- **Call Count**: {domain_info.get('count', 0)}")
            markdown.append(f"- **HTTP Methods**: {', '.join(domain_info.get('methods', []))}")
            markdown.append("")
            
            # Add sample paths
            markdown.append("**Sample Paths:**")
            markdown.append("")
            paths = domain_info.get('paths', [])
            for path in paths[:10]:  # Show only first 10 paths
                markdown.append(f"- `{path}`")
            
            if len(paths) > 10:
                markdown.append(f"- *...and {len(paths) - 10} more*")
            markdown.append("")
        
        # Add authentication methods section if any were detected
        auth_methods_detail = analysis_report.get("auth_methods", {})
        if auth_methods_detail:
            markdown.append("## Authentication Methods")
            markdown.append("")
            
            for auth_type, auth_info in auth_methods_detail.items():
                markdown.append(f"### {auth_info.get('description', auth_type)}")
                markdown.append("")
                if "header" in auth_info:
                    markdown.append(f"**Header:** `{auth_info['header']}`")
                if "parameter" in auth_info:
                    markdown.append(f"**Parameter:** `{auth_info['parameter']}`")
                if "cookie_name" in auth_info:
                    markdown.append(f"**Cookie:** `{auth_info['cookie_name']}`")
                markdown.append("")
                
                # Examples
                if "examples" in auth_info and auth_info["examples"]:
                    markdown.append("**Example:**")
                    markdown.append("```")
                    markdown.append(auth_info["examples"][0])
                    markdown.append("```")
                    markdown.append("")
                
                # Used in endpoints
                if "endpoints" in auth_info and auth_info["endpoints"]:
                    markdown.append("**Used in endpoints:**")
                    for endpoint in auth_info["endpoints"][:5]:  # Show only first 5
                        markdown.append(f"- `{endpoint}`")
                    if len(auth_info["endpoints"]) > 5:
                        markdown.append(f"- *...and {len(auth_info['endpoints']) - 5} more*")
                    markdown.append("")
        
        # Add API endpoints section
        markdown.append("## API Endpoints")
        markdown.append("")
        
        # Sort API endpoints by frequency
        api_endpoints = analysis_report.get("api_endpoints", [])
        
        for i, endpoint in enumerate(api_endpoints):
            method = endpoint.get("method", "UNKNOWN")
            path = endpoint.get("path", "/")
            markdown.append(f"### {i+1}. {method} {path}")
            markdown.append("")
            
            # Basic info
            markdown.append(f"- **Frequency**: {endpoint.get('count', 0)} calls")
            markdown.append(f"- **Full URL**: `{endpoint.get('url', '')}`")
            
            response_codes = endpoint.get("response_codes", [])
            if response_codes:
                markdown.append(f"- **Response Status Codes**: {', '.join(map(str, response_codes))}")
                
            markdown.append("")
            
            # Query Parameters
            query_params = endpoint.get("query_params", {})
            if query_params:
                markdown.append("**Query Parameters:**")
                markdown.append("")
                markdown.append("| Parameter | Example Value |")
                markdown.append("| --- | --- |")
                for param, value in query_params.items():
                    # Format the value, handle complex objects or truncate if too long
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:47] + "..."
                    markdown.append(f"| `{param}` | `{value_str}` |")
                markdown.append("")
            
            # Request Headers
            headers = endpoint.get("headers", {})
            if headers:
                markdown.append("**Request Headers:**")
                markdown.append("")
                markdown.append("| Header | Value |")
                markdown.append("| --- | --- |")
                for header, value in headers.items():
                    # Truncate long header values
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:47] + "..."
                    markdown.append(f"| `{header}` | `{value_str}` |")
                markdown.append("")
            
            # Request Body
            body_params = endpoint.get("body_params", {})
            if body_params:
                markdown.append("**Request Body:**")
                markdown.append("")
                markdown.append("```json")
                try:
                    # Format as JSON if it's a dict, otherwise just print as string
                    if isinstance(body_params, dict) and "raw" not in body_params:
                        markdown.append(json.dumps(body_params, indent=2))
                    else:
                        markdown.append(str(body_params.get("raw", body_params)))
                except Exception:
                    markdown.append(str(body_params))
                markdown.append("```")
                markdown.append("")
        
        # Add REST API patterns section
        api_groups = analysis_report.get("api_groups", {})
        if api_groups:
            markdown.append("## REST API Patterns")
            markdown.append("")
            
            for group_path, group_info in api_groups.items():
                markdown.append(f"### {group_path}")
                markdown.append("")
                markdown.append(f"- **Frequency**: {group_info.get('count', 0)} calls")
                markdown.append(f"- **HTTP Methods**: {', '.join(group_info.get('methods', {}).keys())}")
                markdown.append(f"- **Unique Paths**: {group_info.get('unique_paths', 0)}")
                markdown.append("")
                
                # REST Patterns
                rest_patterns = group_info.get("rest_patterns", [])
                if rest_patterns:
                    markdown.append("**Identified Patterns:**")
                    markdown.append("")
                    for pattern in rest_patterns[:5]:  # Show only first 5
                        pattern_str = pattern.get("pattern", "")
                        count = pattern.get("count", 0)
                        markdown.append(f"- `{pattern_str}` ({count} calls)")
                    if len(rest_patterns) > 5:
                        markdown.append(f"- *...and {len(rest_patterns) - 5} more patterns*")
                    markdown.append("")
        
        # Add response patterns section
        response_patterns = analysis_report.get("response_patterns", {})
        if response_patterns:
            markdown.append("## Response Patterns")
            markdown.append("")
            
            # Status Codes
            status_codes = response_patterns.get("status_codes", {})
            if status_codes:
                markdown.append("### Status Codes")
                markdown.append("")
                markdown.append("| Status Code | Count | Percentage |")
                markdown.append("| --- | --- | --- |")
                total_calls = sum(status_codes.values())
                for code, count in sorted(status_codes.items()):
                    percentage = (count / total_calls) * 100 if total_calls > 0 else 0
                    markdown.append(f"| {code} | {count} | {percentage:.1f}% |")
                markdown.append("")
            
            # Content Types
            content_types = response_patterns.get("content_types", {})
            if content_types:
                markdown.append("### Content Types")
                markdown.append("")
                markdown.append("| Content-Type | Count |")
                markdown.append("| --- | --- |")
                for content_type, count in sorted(content_types.items(), key=lambda x: x[1], reverse=True):
                    markdown.append(f"| `{content_type}` | {count} |")
                markdown.append("")
            
            # JSON Structures
            json_structures = response_patterns.get("json_structures", {})
            if json_structures:
                markdown.append("### Common JSON Response Structures")
                markdown.append("")
                
                for i, (structure_key, structure_info) in enumerate(list(json_structures.items())[:10]):
                    keys = structure_info.get("keys", [])
                    count = structure_info.get("count", 0)
                    example_endpoint = structure_info.get("example_endpoint", "")
                    
                    markdown.append(f"**Pattern {i+1}** (found in {count} responses):")
                    markdown.append("")
                    markdown.append(f"- **Example Endpoint**: `{example_endpoint}`")
                    markdown.append(f"- **Properties**: {', '.join([f'`{key}`' for key in keys])}")
                    markdown.append("")
                
                if len(json_structures) > 10:
                    markdown.append(f"*...and {len(json_structures) - 10} more response patterns*")
                    markdown.append("")
        
        # Add errors section
        error_patterns = analysis_report.get("error_patterns", {})
        if error_patterns:
            markdown.append("## Error Responses")
            markdown.append("")
            
            for status_code, error_info in error_patterns.items():
                markdown.append(f"### Status Code {status_code}")
                markdown.append("")
                markdown.append(f"- **Frequency**: {error_info.get('count', 0)} occurrences")
                markdown.append("")
                
                # Examples
                examples = error_info.get("examples", [])
                if examples:
                    for i, example in enumerate(examples):
                        markdown.append(f"**Example {i+1}:**")
                        markdown.append("")
                        markdown.append(f"- **Path**: `{example.get('path', '')}`")
                        markdown.append(f"- **Method**: {example.get('method', '')}")
                        
                        # Error structure
                        structure = example.get("structure", {})
                        if structure:
                            markdown.append("")
                            markdown.append("```json")
                            try:
                                markdown.append(json.dumps(structure, indent=2))
                            except Exception:
                                markdown.append(str(structure))
                            markdown.append("```")
                        markdown.append("")
        
        # Join all lines and return
        return "\n".join(markdown)
    
    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format file size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
        
    @staticmethod
    def convert_report_to_markdown(report_name: str, report_data: Dict[str, Any]) -> str:
        """
        Convert any analysis report to markdown format
        
        Args:
            report_name: Name of the analysis report
            report_data: Dictionary containing the report data
            
        Returns:
            Markdown formatted string
        """
        markdown = []
        
        # Add header
        markdown.append(f"# {report_name}")
        markdown.append("")
        markdown.append(f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        markdown.append("")
        
        # Process basic file info if present
        if "har_file" in report_data:
            file_info = report_data["har_file"]
            markdown.append("## File Information")
            markdown.append("")
            if "filename" in file_info:
                markdown.append(f"- **Filename**: {file_info['filename']}")
            if "file_size" in file_info:
                markdown.append(f"- **Size**: {DocumentationGenerator._format_file_size(file_info['file_size'])}")
            if "browser" in file_info:
                browser_text = file_info['browser']
                if "browser_version" in file_info and file_info["browser_version"]:
                    browser_text += f" {file_info['browser_version']}"
                markdown.append(f"- **Browser**: {browser_text}")
            markdown.append("")
        
        # Process the report data recursively
        DocumentationGenerator._process_report_section(markdown, report_data, 2)
        
        return "\n".join(markdown)
    
    @staticmethod
    def _process_report_section(markdown: List[str], data: Any, level: int) -> None:
        """
        Recursively process a section of the report data
        
        Args:
            markdown: List of markdown lines to append to
            data: Data to process
            level: Current header level
        """
        if isinstance(data, dict):
            for key, value in data.items():
                # Skip har_file which was processed separately
                if key == "har_file":
                    continue
                    
                # Format key as header
                header_prefix = "#" * level
                # Convert key to string to ensure we can call replace on it
                key_str = str(key).replace('_', ' ').title()
                markdown.append(f"{header_prefix} {key_str}")
                markdown.append("")
                
                if isinstance(value, (dict, list)) and value:
                    DocumentationGenerator._process_report_section(markdown, value, level + 1)
                else:
                    markdown.append(f"{value}")
                    markdown.append("")
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    # If dictionary has a name or title, use it
                    item_name = item.get("name", item.get("title", f"Item {i+1}"))
                    header_prefix = "#" * level
                    markdown.append(f"{header_prefix} {item_name}")
                    markdown.append("")
                    DocumentationGenerator._process_report_section(markdown, item, level + 1)
                else:
                    markdown.append(f"- {item}")
            markdown.append("")
        else:
            # Convert to string to handle non-string types
            markdown.append(f"{str(data)}")
            markdown.append("")


class PostmanCollectionGenerator:
    """
    Service for generating Postman collection export based on HAR file analysis.
    """
    
    @staticmethod
    def generate_collection(har_file: HARFile, analysis_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a Postman collection from HAR file analysis.
        
        Args:
            har_file: The HAR file model
            analysis_report: The analysis report from HARAnalyzer
            
        Returns:
            Dictionary representing a Postman collection
        """
        # Create collection structure
        collection = {
            "info": {
                "name": f"{har_file.filename} API Collection",
                "description": f"Generated from HAR file analysis on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }
        
        # Group endpoints by domain and path
        domains = analysis_report.get("domains", {})
        api_endpoints = analysis_report.get("api_endpoints", [])
        
        # First, organize by domains
        domain_folders = {}
        for domain, domain_info in domains.items():
            domain_folders[domain] = {
                "name": domain,
                "item": []
            }
        
        # Then create request items and add them to the appropriate domain folder
        for endpoint in api_endpoints:
            method = endpoint.get("method", "GET")
            url = endpoint.get("url", "")
            path = endpoint.get("path", "")
            
            # Extract domain from URL
            domain = urlparse(url).netloc
            
            # Create request item
            request_item = {
                "name": f"{method} {path}",
                "request": {
                    "method": method,
                    "header": [],
                    "url": {
                        "raw": url,
                        "protocol": urlparse(url).scheme,
                        "host": domain.split("."),
                        "path": path.strip("/").split("/")
                    }
                },
                "response": []
            }
            
            # Add query params if any
            query_params = endpoint.get("query_params", {})
            if query_params:
                request_item["request"]["url"]["query"] = []
                for key, value in query_params.items():
                    request_item["request"]["url"]["query"].append({
                        "key": key,
                        "value": str(value),
                        "disabled": False
                    })
            
            # Add headers if any
            headers = endpoint.get("headers", {})
            for header_name, header_value in headers.items():
                request_item["request"]["header"].append({
                    "key": header_name,
                    "value": header_value,
                    "type": "text"
                })
            
            # Add body if any
            body_params = endpoint.get("body_params", {})
            if body_params:
                if isinstance(body_params, dict) and "raw" not in body_params:
                    # JSON body
                    request_item["request"]["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(body_params, indent=2),
                        "options": {
                            "raw": {
                                "language": "json"
                            }
                        }
                    }
                else:
                    # String/raw body
                    raw_body = body_params.get("raw", str(body_params))
                    request_item["request"]["body"] = {
                        "mode": "raw",
                        "raw": raw_body
                    }
            
            # Add to domain folder
            if domain in domain_folders:
                domain_folders[domain]["item"].append(request_item)
            else:
                # If domain not found, add to a misc folder
                if "misc" not in domain_folders:
                    domain_folders["misc"] = {
                        "name": "Miscellaneous",
                        "item": []
                    }
                domain_folders["misc"]["item"].append(request_item)
        
        # Add all domain folders to collection
        collection["item"] = list(domain_folders.values())
        
        return collection


class APIPatternEnhancer:
    """
    Service for enhancing API pattern detection and identifying similar APIs
    """
    
    @staticmethod
    def enhance_pattern_detection(api_calls: List[Any]) -> Dict[str, Any]:
        """
        Enhance API pattern detection with more advanced techniques.
        
        Args:
            api_calls: List of API calls from the database
            
        Returns:
            Enhanced pattern information
        """
        # Path parameter detection with advanced patterns
        path_parameters = APIPatternEnhancer._detect_path_parameters(api_calls)
        
        # Endpoint purpose classification
        endpoint_purposes = APIPatternEnhancer._classify_endpoints(api_calls)
        
        # Temporal patterns (sequence of calls)
        temporal_patterns = APIPatternEnhancer._detect_temporal_patterns(api_calls)
        
        # Resource relationships
        resource_relationships = APIPatternEnhancer._detect_resource_relationships(api_calls)
        
        return {
            "path_parameters": path_parameters,
            "endpoint_purposes": endpoint_purposes,
            "temporal_patterns": temporal_patterns,
            "resource_relationships": resource_relationships
        }
    
    @staticmethod
    def detect_similar_apis(api_calls: List[Any]) -> List[Dict[str, Any]]:
        """
        Detect similar APIs based on various similarity measures.
        
        Args:
            api_calls: List of API calls from the database
            
        Returns:
            List of similar API groups
        """
        # Group endpoints with similar paths
        path_similarity = APIPatternEnhancer._group_by_path_similarity(api_calls)
        
        # Group endpoints with similar request/response structures
        structure_similarity = APIPatternEnhancer._group_by_structure_similarity(api_calls)
        
        # Group endpoints with similar parameters
        parameter_similarity = APIPatternEnhancer._group_by_parameter_similarity(api_calls)
        
        # Combine similarity measures
        combined_similarity = APIPatternEnhancer._combine_similarity_measures(
            path_similarity, structure_similarity, parameter_similarity
        )
        
        return combined_similarity
    
    @staticmethod
    def _detect_path_parameters(api_calls: List[Any]) -> Dict[str, Any]:
        """Detect path parameters with more advanced patterns"""
        path_params = {}
        
        # Group paths by pattern (removing potential IDs)
        path_patterns = {}
        
        # Common parameter patterns
        param_patterns = {
            'uuid': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            'numeric_id': r'\d+',
            'alphanum_id': r'[a-zA-Z0-9]+',
            'hash': r'[0-9a-f]{24,40}',
            'date': r'\d{4}-\d{2}-\d{2}',
            'slug': r'[a-z0-9]+(?:-[a-z0-9]+)*'
        }
        
        # To be implemented with more sophisticated pattern analysis
        return {
            "detected_parameter_types": list(param_patterns.keys()),
            "parameter_examples": {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "numeric_id": "123456",
                "alphanum_id": "a1b2c3d4",
                "hash": "5f2d56c41d5e4d0a3a8f1c91",
                "date": "2023-05-15",
                "slug": "api-endpoint-name"
            }
        }
    
    @staticmethod
    def _classify_endpoints(api_calls: List[Any]) -> Dict[str, Any]:
        """Classify endpoints by their likely purpose"""
        # CRUD operations mapping
        crud_patterns = {
            "create": ["POST"],
            "read": ["GET"],
            "update": ["PUT", "PATCH"],
            "delete": ["DELETE"]
        }
        
        # Authentication patterns
        auth_patterns = [
            "/login", "/auth", "/token", "/signin", "/oauth", "/logout", "/signout"
        ]
        
        # Search/filtering patterns
        search_patterns = [
            "/search", "/filter", "/query", "list", "find"
        ]
        
        # To be implemented with more sophisticated classification logic
        return {
            "classification_categories": ["CRUD", "Authentication", "Search", "Upload", "Download", "Reporting"],
            "common_patterns": {
                "Authentication": auth_patterns,
                "Search": search_patterns
            }
        }
    
    @staticmethod
    def _detect_temporal_patterns(api_calls: List[Any]) -> Dict[str, Any]:
        """Detect temporal patterns and sequences in API calls"""
        # To be implemented with time-based sequence analysis
        return {
            "sequence_examples": [
                ["GET /api/users", "GET /api/users/{id}", "PUT /api/users/{id}"],
                ["POST /api/auth/login", "GET /api/user/profile", "GET /api/resources"]
            ],
            "common_workflows": {
                "Authentication flow": ["POST /auth/login", "GET /user/profile"],
                "Resource creation": ["GET /resources", "POST /resources", "GET /resources/{id}"]
            }
        }
    
    @staticmethod
    def _detect_resource_relationships(api_calls: List[Any]) -> Dict[str, Any]:
        """Detect relationships between different API resources"""
        # To be implemented with resource relationship analysis
        return {
            "identified_resources": ["users", "posts", "comments", "products", "orders"],
            "relationship_examples": {
                "users-posts": "one-to-many",
                "posts-comments": "one-to-many",
                "users-orders": "one-to-many",
                "orders-products": "many-to-many"
            }
        }
    
    @staticmethod
    def _group_by_path_similarity(api_calls: List[Any]) -> List[Dict[str, Any]]:
        """Group endpoints by path similarity"""
        # To be implemented with path-based similarity measures
        return [
            {
                "group": "User management",
                "similarity_score": 0.85,
                "endpoints": ["/api/users", "/api/users/{id}", "/api/users/{id}/profile"]
            },
            {
                "group": "Content management",
                "similarity_score": 0.78,
                "endpoints": ["/api/posts", "/api/posts/{id}", "/api/comments"]
            }
        ]
    
    @staticmethod
    def _group_by_structure_similarity(api_calls: List[Any]) -> List[Dict[str, Any]]:
        """Group endpoints by request/response structure similarity"""
        # To be implemented with structure-based similarity measures
        return [
            {
                "group": "Paginated responses",
                "similarity_score": 0.92,
                "common_fields": ["items", "page", "total", "limit"],
                "endpoints": ["/api/users", "/api/posts", "/api/products"]
            }
        ]
    
    @staticmethod
    def _group_by_parameter_similarity(api_calls: List[Any]) -> List[Dict[str, Any]]:
        """Group endpoints by parameter similarity"""
        # To be implemented with parameter-based similarity measures
        return [
            {
                "group": "Filtered queries",
                "similarity_score": 0.88,
                "common_parameters": ["filter", "sort", "limit", "offset"],
                "endpoints": ["/api/users", "/api/posts", "/api/products"]
            }
        ]
    
    @staticmethod
    def _combine_similarity_measures(
        path_similarity: List[Dict[str, Any]],
        structure_similarity: List[Dict[str, Any]],
        parameter_similarity: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Combine different similarity measures into overall API groupings"""
        # To be implemented with a combined similarity approach
        return [
            {
                "group": "Resource listing APIs",
                "overall_similarity_score": 0.85,
                "endpoints": ["/api/users", "/api/posts", "/api/products"],
                "similarity_factors": ["path pattern", "response structure", "query parameters"]
            },
            {
                "group": "Resource detail APIs",
                "overall_similarity_score": 0.90,
                "endpoints": ["/api/users/{id}", "/api/posts/{id}", "/api/products/{id}"],
                "similarity_factors": ["path pattern", "parameter types"]
            }
        ] 