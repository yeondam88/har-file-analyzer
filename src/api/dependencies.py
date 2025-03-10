from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.exceptions import CredentialsException
from src.db.session import get_db
from src.models.user import User
from src.schemas.user import TokenPayload

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/auth/login", auto_error=False)

# Test user for bypassing authentication (only for testing)
TEST_USER_ID = "test-user-id"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_USERNAME = "testuser"

"""
# Original authentication function - commented out for testing
def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    \"""
    Get the current authenticated user from the token.
    
    Args:
        db: Database session
        token: JWT token
        
    Returns:
        User object if authenticated
        
    Raises:
        CredentialsException: If authentication fails
    \"""
    try:
        # Decode the token
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise CredentialsException()
    
    # Get the user from the database
    user = db.query(User).filter(User.id == token_data.sub).first()
    if not user:
        raise CredentialsException()
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user
"""

# Test version for bypassing authentication
def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    For testing: Return a test user without authentication
    """
    # Check if user exists in DB, if not create one
    user = db.query(User).filter(User.username == TEST_USER_USERNAME).first()
    if not user:
        # Create a test user
        user = User(
            id=TEST_USER_ID,
            email=TEST_USER_EMAIL,
            username=TEST_USER_USERNAME,
            hashed_password="test_hashed_password",  # Not used for testing
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

"""
# Original active user check - commented out for testing
def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    \"""
    Check if the current user is active.
    
    Args:
        current_user: User from get_current_user
        
    Returns:
        User object if active
        
    Raises:
        HTTPException: If user is inactive
    \"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
"""

# Test version for bypassing authentication
def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    For testing: Return the test user without checking if active
    """
    return current_user

"""
# Original superuser check - commented out for testing
def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    \"""
    Check if the current user is a superuser.
    
    Args:
        current_user: User from get_current_user
        
    Returns:
        User object if superuser
        
    Raises:
        HTTPException: If user is not a superuser
    \"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user
"""

# Test version for bypassing authentication
def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    For testing: Return the test user without checking if superuser
    """
    return current_user 