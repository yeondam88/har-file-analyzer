from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.api.dependencies import get_current_active_user
from src.db.session import get_db
from src.models.api_call import APICall
from src.models.har_file import HARFile
from src.models.user import User
from src.schemas.api_call import (
    APICall as APICallSchema,
    APICallList,
    APICallReplayRequest,
    APICallReplayResponse,
)
from src.services.api_replayer import APIReplayer

router = APIRouter()


@router.get("", response_model=APICallList)
def list_api_calls(
    db: Session = Depends(get_db),
    har_file_id: Optional[str] = None,
    method: Optional[str] = None,
    path_contains: Optional[str] = None,
    is_xhr: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    List API calls with filtering options.
    """
    # Base query
    query = db.query(APICall).join(HARFile).filter(HARFile.user_id == current_user.id)
    
    # Apply filters
    if har_file_id:
        query = query.filter(APICall.har_file_id == har_file_id)
    
    if method:
        query = query.filter(APICall.method == method.upper())
    
    if path_contains:
        query = query.filter(APICall.path.contains(path_contains))
    
    if is_xhr is not None:
        query = query.filter(APICall.is_xhr == is_xhr)
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination
    api_calls = query.offset(skip).limit(limit).all()
    
    return APICallList(items=api_calls, total=total)


@router.get("/{call_id}", response_model=APICallSchema)
def get_api_call(
    *,
    db: Session = Depends(get_db),
    call_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a specific API call by ID.
    """
    # Get API call with ownership check
    api_call = (
        db.query(APICall)
        .join(HARFile)
        .filter(APICall.id == call_id, HARFile.user_id == current_user.id)
        .first()
    )
    
    if not api_call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API call not found",
        )
    
    return api_call


@router.post("/{call_id}/replay", response_model=APICallReplayResponse)
def replay_api_call(
    *,
    db: Session = Depends(get_db),
    call_id: str,
    replay_request: APICallReplayRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Replay an API call.
    """
    # Get API call with ownership check
    api_call = (
        db.query(APICall)
        .join(HARFile)
        .filter(APICall.id == call_id, HARFile.user_id == current_user.id)
        .first()
    )
    
    if not api_call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API call not found",
        )
    
    # Replay API call
    replayer = APIReplayer(db)
    response = replayer.replay_api_call(call_id=call_id, replay_request=replay_request)
    
    return response


@router.get("/methods", response_model=List[str])
def get_api_call_methods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get a list of available HTTP methods in the user's API calls.
    """
    methods = (
        db.query(APICall.method)
        .join(HARFile)
        .filter(HARFile.user_id == current_user.id)
        .distinct()
        .all()
    )
    
    return [method[0] for method in methods]


@router.get("/stats", response_model=Dict[str, Any])
def get_api_call_stats(
    db: Session = Depends(get_db),
    har_file_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get statistics about API calls.
    """
    # Base query
    query = db.query(APICall).join(HARFile).filter(HARFile.user_id == current_user.id)
    
    # Apply HAR file filter if provided
    if har_file_id:
        query = query.filter(APICall.har_file_id == har_file_id)
    
    # Get stats
    total_count = query.count()
    
    # Count by method
    method_counts = (
        db.query(APICall.method, func.count(APICall.id))
        .join(HARFile)
        .filter(HARFile.user_id == current_user.id)
    )
    
    if har_file_id:
        method_counts = method_counts.filter(APICall.har_file_id == har_file_id)
    
    method_counts = method_counts.group_by(APICall.method).all()
    
    # Count by response status
    status_counts = (
        db.query(APICall.response_status, func.count(APICall.id))
        .join(HARFile)
        .filter(HARFile.user_id == current_user.id)
    )
    
    if har_file_id:
        status_counts = status_counts.filter(APICall.har_file_id == har_file_id)
    
    status_counts = status_counts.group_by(APICall.response_status).all()
    
    return {
        "total": total_count,
        "methods": {method: count for method, count in method_counts},
        "statuses": {status: count for status, count in status_counts},
    } 