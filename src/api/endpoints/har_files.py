import json
from typing import Any, Dict, List
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_active_user
from src.db.session import get_db
from src.models.har_file import HARFile
from src.models.api_call import APICall
from src.models.user import User
from src.schemas.har_file import HARFile as HARFileSchema, HARFileCreate, HARFileWithCount
from src.services.har_parser import HARParser
from src.services.har_analyzer import HARAnalyzer
from src.services.documentation_generator import DocumentationGenerator, PostmanCollectionGenerator, APIPatternEnhancer

router = APIRouter()


def create_markdown_response(har_file: HARFile, report: Dict[str, Any], report_type: str, download: bool = False) -> Response:
    """
    Utility function to create a consistent markdown response
    
    Args:
        har_file: The HAR file model
        report: The analysis report data
        report_type: Type of report (for filename)
        download: Whether to force download the file (True) or display inline (False)
        
    Returns:
        FastAPI Response with markdown content
    """
    try:
        # Ensure report contains har_file info if not present
        if "har_file" not in report:
            report["har_file"] = {
                "id": har_file.id,
                "filename": har_file.filename,
                "file_size": har_file.file_size,
                "browser": har_file.browser,
                "browser_version": har_file.browser_version,
            }
            
        # Convert report to markdown
        report_title = f"{report_type.replace('-', ' ').title()} Analysis for {har_file.filename}"
        markdown = DocumentationGenerator.convert_report_to_markdown(report_title, report)
        
        # Generate filename
        base_filename = har_file.filename.split('.')[0]
        filename = f"{base_filename}_{report_type.replace('-', '_')}.md"
        
        # Set content disposition based on download parameter
        disposition = "attachment" if download else "inline"
        
        # Return as a downloadable or viewable file
        return Response(
            content=markdown,
            media_type="text/markdown", 
            headers={
                "Content-Disposition": f"{disposition}; filename={filename}"
            }
        )
    except Exception as e:
        # Log the error
        logging.error(f"Error generating markdown response: {str(e)}")
        # Return error message as markdown
        error_markdown = f"""# Error Generating {report_type.replace('-', ' ').title()} Report

Unfortunately, an error occurred while generating the markdown report:

```
{str(e)}
```

Please try again or contact support if the issue persists.
"""
        return Response(
            content=error_markdown,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"inline; filename=error_{report_type.replace('-', '_')}.md"
            }
        )


@router.post("", response_model=HARFileSchema)
async def upload_har_file(
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    description: str = Query(None),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Upload a new HAR file and parse its contents.
    """
    # Validate file
    if not file.filename.lower().endswith(".har"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a HAR file",
        )
    
    # Read file content
    content = await file.read()
    
    # Parse HAR file
    har_parser = HARParser(db)
    har_file_obj = HARFileCreate(filename=file.filename, description=description)
    
    # Process the file
    har_file, api_calls = har_parser.parse_har_file(
        content=content,
        filename=file.filename,
        user_id=current_user.id,
    )
    
    return har_file


@router.get("", response_model=List[HARFileWithCount])
def list_har_files(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve HAR files uploaded by the current user.
    """
    # Get HAR files
    har_files = (
        db.query(HARFile)
        .filter(HARFile.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    # Add API call count to each HAR file
    result = []
    for har_file in har_files:
        api_call_count = len(har_file.api_calls)
        har_file_with_count = HARFileWithCount(
            id=har_file.id,
            filename=har_file.filename,
            description=har_file.description,
            user_id=har_file.user_id,
            file_size=har_file.file_size,
            browser=har_file.browser,
            browser_version=har_file.browser_version,
            created_at=har_file.created_at,
            updated_at=har_file.updated_at,
            api_call_count=api_call_count,
        )
        result.append(har_file_with_count)
    
    return result


@router.get("/{har_file_id}", response_model=HARFileSchema)
def get_har_file(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific HAR file by ID.
    """
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    return har_file


@router.delete("/{har_file_id}")
def delete_har_file(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a HAR file.
    """
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Delete the HAR file (and associated API calls due to cascade)
    db.delete(har_file)
    db.commit()
    
    return {"message": "HAR file deleted successfully"}


@router.get("/{har_file_id}/analyze", response_model=Dict[str, Any])
def analyze_har_file(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Generate a comprehensive analysis report for a HAR file.
    
    This endpoint extracts detailed information about:
    - API endpoints and patterns
    - Authentication methods
    - Common headers and cookies
    - Response patterns and structures
    - Error patterns
    - Domain information
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Generate analysis report
    try:
        analyzer = HARAnalyzer(db)
        report = analyzer.generate_report(har_file_id)
        
        # Return based on requested format
        if format.lower() == "markdown":
            return create_markdown_response(har_file, report, "general-analysis", download)
        else:
            return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}",
        )


@router.get("/{har_file_id}/analyze/auth", response_model=Dict[str, Any])
def analyze_har_file_auth(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Analyze authentication patterns in a HAR file.
    
    This endpoint focuses on authentication details:
    - Authentication methods used (Basic, Bearer, API Key, OAuth, etc.)
    - Token patterns and locations
    - Cookie-based authentication
    - Authentication flows
    - Security headers
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Generate auth analysis
    try:
        analyzer = HARAnalyzer(db)
        report = analyzer.analyze_auth(har_file_id)
        
        # Return based on requested format
        if format.lower() == "markdown":
            return create_markdown_response(har_file, report, "auth-analysis", download)
        else:
            return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing authentication: {str(e)}",
        )


@router.get("/{har_file_id}/analyze/endpoints", response_model=Dict[str, Any])
def analyze_har_file_endpoints(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Analyze API endpoints in a HAR file.
    
    This endpoint focuses on endpoint details:
    - List of unique endpoints
    - HTTP methods used
    - Query parameters across endpoints
    - Request body patterns
    - Response status codes
    - Response content types
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Generate endpoints analysis
    try:
        # First check if we need to implement a specific analyzer function
        analyzer = HARAnalyzer(db)
        if hasattr(analyzer, "analyze_endpoints") and callable(getattr(analyzer, "analyze_endpoints")):
            report = analyzer.analyze_endpoints(har_file_id)
        else:
            # Fall back to general report
            report = analyzer.generate_report(har_file_id)
            # Extract only endpoint-related sections
            report = {
                "har_file": report["har_file"],
                "api_count": report["api_count"],
                "unique_endpoints": report["unique_endpoints"],
                "http_methods": report["http_methods"],
                "endpoint_details": report.get("endpoint_details", {})
            }
        
        # Return based on requested format
        if format.lower() == "markdown":
            return create_markdown_response(har_file, report, "endpoints-analysis", download)
        else:
            return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing endpoints: {str(e)}",
        )


@router.get("/{har_file_id}/export/markdown")
def export_markdown_documentation(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    download: bool = Query(True, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Export HAR file analysis as markdown documentation.
    
    This endpoint generates a comprehensive markdown document with:
    - API endpoints details
    - Authentication methods
    - Request/response patterns
    - Error responses
    - And more...
    
    The output can be saved as a .md file and viewed in any markdown reader.
    
    Parameters:
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Generate analysis and convert to markdown
    try:
        analyzer = HARAnalyzer(db)
        report = analyzer.generate_report(har_file_id)
        
        # Generate markdown
        markdown = DocumentationGenerator.generate_markdown(har_file, report)
        
        # Set content disposition based on download parameter
        disposition = "attachment" if download else "inline"
        
        # Return as a downloadable or viewable file
        filename = f"{har_file.filename.split('.')[0]}_api_docs.md"
        return Response(
            content=markdown,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"{disposition}; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating markdown documentation: {str(e)}",
        )


@router.get("/{har_file_id}/export/postman")
def export_postman_collection(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    download: bool = Query(True, description="Force download the JSON file instead of displaying in browser")
) -> Any:
    """
    Export HAR file analysis as a Postman collection.
    
    This endpoint generates a Postman collection with:
    - API endpoints organized by domain
    - HTTP methods and headers
    - Query parameters and request bodies
    - Examples based on the HAR file data
    
    The output can be imported directly into Postman.
    
    Parameters:
        download: Whether to download the JSON file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Generate Postman collection
    try:
        analyzer = HARAnalyzer(db)
        report = analyzer.generate_report(har_file_id)
        
        # Generate Postman collection
        collection = PostmanCollectionGenerator.generate_collection(har_file, report)
        
        # Set content disposition based on download parameter
        disposition = "attachment" if download else "inline"
        
        # Return as a downloadable or viewable file
        filename = f"{har_file.filename.split('.')[0]}_postman_collection.json"
        return Response(
            content=json.dumps(collection, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f"{disposition}; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating Postman collection: {str(e)}",
        )


@router.get("/{har_file_id}/analyze/enhanced-patterns", response_model=Dict[str, Any])
def analyze_har_file_enhanced_patterns(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Perform enhanced pattern detection on HAR file.
    
    This endpoint provides advanced pattern analysis:
    - Path parameter detection (UUIDs, IDs, slugs)
    - Endpoint purpose classification
    - Temporal patterns in API call sequences
    - Resource relationships
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    # Generate enhanced pattern analysis
    try:
        # Get API calls
        api_calls = db.query(APICall).filter(APICall.har_file_id == har_file_id).all()
        
        # Convert API calls to a format that APIPatternEnhancer can use
        api_calls_data = []
        for call in api_calls:
            # Create a simplified representation of the API call
            call_data = {
                "url": call.url,
                "method": call.method,
                "path": urlparse(call.url).path,
                "query": urlparse(call.url).query,
                "request_headers": json.loads(call.request_headers) if hasattr(call, 'request_headers') and call.request_headers else {},
                "request_body": call.request_body if hasattr(call, 'request_body') else None,
                "response_headers": json.loads(call.response_headers) if hasattr(call, 'response_headers') and call.response_headers else {},
                "status_code": call.status_code if hasattr(call, 'status_code') else None
            }
            api_calls_data.append(call_data)
        
        # Generate enhanced pattern report
        har_file_info = {
            "id": har_file.id,
            "filename": har_file.filename,
            "file_size": har_file.file_size,
            "browser": har_file.browser,
            "browser_version": har_file.browser_version,
        }
        
        report = {
            "har_file": har_file_info,
            "patterns": APIPatternEnhancer.enhance_pattern_detection(api_calls_data)
        }
        
        # Return based on requested format
        if format.lower() == "markdown":
            return create_markdown_response(har_file, report, "enhanced-patterns", download)
        else:
            return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing enhanced patterns: {str(e)}",
        )


@router.get("/{har_file_id}/report/general", response_model=Dict[str, Any])
def generate_general_report(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Generate a general analysis report for a HAR file.
    
    This endpoint provides a comprehensive overview of the HAR file analysis:
    - Basic file information
    - API endpoints summary
    - Domain statistics
    - HTTP methods distribution
    - Common response patterns
    - Authentication methods used
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    try:
        # Use HAR Analyzer to generate a comprehensive report
        analyzer = HARAnalyzer(db)
        report = analyzer.generate_report(har_file_id)
        
        # Add HAR file information
        har_file_info = {
            "id": har_file.id,
            "filename": har_file.filename,
            "file_size": har_file.file_size,
            "browser": har_file.browser,
            "browser_version": har_file.browser_version,
            "created_at": har_file.created_at.isoformat() if har_file.created_at else None,
        }
        
        # Combine everything into a general report
        general_report = {
            "har_file": har_file_info,
            "summary": report.get("summary", {}),
            "domains": report.get("domains", {}),
            "auth_methods": report.get("auth_methods", {})
        }
        
        # Return based on requested format
        if format.lower() == "markdown":
            return create_markdown_response(har_file, general_report, "general", download)
        else:
            return general_report
    except Exception as e:
        logger.error(f"Error generating general report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating general report: {str(e)}",
        )


@router.get("/{har_file_id}/report/auth", response_model=Dict[str, Any])
def generate_auth_report(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Generate an authentication analysis report for a HAR file.
    
    This endpoint provides detailed information about authentication methods:
    - Token-based authentication
    - Basic authentication
    - Cookie-based authentication
    - API key authentication
    - OAuth flows
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    return analyze_har_file_auth(
        db=db,
        har_file_id=har_file_id,
        current_user=current_user,
        format=format,
        download=download
    )


@router.get("/{har_file_id}/report/endpoints", response_model=Dict[str, Any])
def generate_endpoints_report(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Generate an endpoints analysis report for a HAR file.
    
    This endpoint provides detailed information about API endpoints:
    - URL patterns
    - HTTP methods
    - Request parameters
    - Response status codes
    - Common response structures
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    return analyze_har_file_endpoints(
        db=db,
        har_file_id=har_file_id,
        current_user=current_user,
        format=format,
        download=download
    )


@router.get("/{har_file_id}/report/enhanced-patterns", response_model=Dict[str, Any])
def generate_enhanced_patterns_report(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Generate an enhanced patterns analysis report for a HAR file.
    
    This endpoint provides advanced pattern analysis:
    - Path parameter detection (UUIDs, IDs, slugs)
    - Endpoint purpose classification
    - Temporal patterns in API call sequences
    - Resource relationships
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    return analyze_har_file_enhanced_patterns(
        db=db,
        har_file_id=har_file_id,
        current_user=current_user,
        format=format,
        download=download
    )


@router.get("/{har_file_id}/analyze/similar-apis", response_model=Dict[str, Any])
def analyze_har_file_similar_apis(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Identify similar API endpoints in a HAR file based on various similarity metrics.
    
    This endpoint groups API calls based on similarity:
    - Path similarity (endpoints with similar structures)
    - Request/response structure similarity
    - Parameter similarity
    - Combined similarity scoring
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Get HAR file
    har_file = db.query(HARFile).filter(HARFile.id == har_file_id).first()
    
    if not har_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HAR file not found",
        )
    
    # Check ownership
    if har_file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    
    try:
        # Get API calls
        api_calls = db.query(APICall).filter(APICall.har_file_id == har_file_id).all()
        
        # Convert API calls to a format that APIPatternEnhancer can use
        api_calls_data = []
        for call in api_calls:
            # Create a simplified representation of the API call
            call_data = {
                "url": call.url,
                "method": call.method,
                "path": urlparse(call.url).path,
                "query": urlparse(call.url).query,
                "request_headers": json.loads(call.request_headers) if hasattr(call, 'request_headers') and call.request_headers else {},
                "request_body": call.request_body if hasattr(call, 'request_body') else None,
                "response_headers": json.loads(call.response_headers) if hasattr(call, 'response_headers') and call.response_headers else {},
                "status_code": call.status_code if hasattr(call, 'status_code') else None
            }
            api_calls_data.append(call_data)
        
        # Generate similar APIs report
        har_file_info = {
            "id": har_file.id,
            "filename": har_file.filename,
            "file_size": har_file.file_size,
            "browser": har_file.browser,
            "browser_version": har_file.browser_version,
        }
        
        # Use APIPatternEnhancer to find similar APIs
        similar_apis = APIPatternEnhancer.find_similar_apis(api_calls_data)
        
        report = {
            "har_file": har_file_info,
            "similar_apis": similar_apis
        }
        
        # Return based on requested format
        if format.lower() == "markdown":
            return create_markdown_response(har_file, report, "similar-apis", download)
        else:
            return report
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing similar APIs: {str(e)}",
        )


@router.get("/{har_file_id}/report/similar-apis", response_model=Dict[str, Any])
def generate_similar_apis_report(
    *,
    db: Session = Depends(get_db),
    har_file_id: str,
    current_user: User = Depends(get_current_active_user),
    format: str = Query("json", description="Output format: json or markdown"),
    download: bool = Query(False, description="Force download the markdown file instead of displaying in browser")
) -> Any:
    """
    Generate a similar APIs analysis report for a HAR file.
    
    This endpoint groups API calls based on similarity:
    - Path similarity (endpoints with similar structures)
    - Request/response structure similarity
    - Parameter similarity
    - Combined similarity scoring
    
    Parameters:
        format: Output format, either 'json' or 'markdown'
        download: Whether to download the markdown file (True) or display inline (False)
    """
    # Use the implementation from analyze_har_file_similar_apis
    return analyze_har_file_similar_apis(
        db=db,
        har_file_id=har_file_id,
        current_user=current_user,
        format=format,
        download=download
    ) 