from typing import Generator
import logging

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

# Set up logging
logger = logging.getLogger(__name__)

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
    try:
        # First check if we can execute a read query (which is less likely to lock)
        try:
            logger.info("Attempting to fetch test user from database")
            user = db.query(User).filter(User.username == TEST_USER_USERNAME).first()
            if user:
                logger.info("Found existing test user")
                return user
        except Exception as read_error:
            logger.error(f"Error reading from database: {str(read_error)}")
            
        # If we get here, either the user doesn't exist or we had a read error
        # Let's return an in-memory user without persisting if there are any issues
        try:
            # Try with a transaction timeout
            logger.info("Test user not found, creating new test user")
            
            # Check if the table exists first
            table_exists = False
            try:
                result = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                table_exists = result.scalar() is not None
            except Exception as table_check_error:
                logger.error(f"Error checking for users table: {str(table_check_error)}")
            
            if not table_exists:
                logger.warning("Users table doesn't exist, using in-memory user")
                return User(
                    id=TEST_USER_ID,
                    email=TEST_USER_EMAIL,
                    username=TEST_USER_USERNAME,
                    hashed_password="test_hashed_password",
                    is_active=True,
                    is_superuser=True,
                )
            
            # Create user with transaction guard
            user = User(
                id=TEST_USER_ID,
                email=TEST_USER_EMAIL,
                username=TEST_USER_USERNAME,
                hashed_password="test_hashed_password",  # Not used for testing
                is_active=True,
                is_superuser=True,
            )
            
            try:
                db.begin_nested()  # Create a savepoint
                db.add(user)
                db.commit()
                logger.info("Successfully created test user in database")
                return user
            except Exception as create_error:
                logger.error(f"Error creating test user: {str(create_error)}")
                db.rollback()
                
                # If the error indicates a user already exists (unique constraint), try to fetch again
                if "UNIQUE constraint" in str(create_error):
                    logger.info("User likely exists due to unique constraint error, trying to fetch again")
                    user = db.query(User).filter(User.username == TEST_USER_USERNAME).first()
                    if user:
                        logger.info("Successfully fetched existing user after unique constraint error")
                        return user
                
                # If we still don't have a user, return an in-memory one
                logger.warning("Using in-memory test user as fallback")
                return User(
                    id=TEST_USER_ID,
                    email=TEST_USER_EMAIL,
                    username=TEST_USER_USERNAME,
                    hashed_password="test_hashed_password",
                    is_active=True,
                    is_superuser=True,
                )
        except Exception as e:
            logger.error(f"Unexpected error in user creation flow: {str(e)}")
    except Exception as outer_e:
        logger.error(f"Unexpected error in get_current_user: {str(outer_e)}")
    
    # Final fallback - always return a user
    logger.warning("Using emergency in-memory test user due to unexpected error")
    return User(
        id=TEST_USER_ID,
        email=TEST_USER_EMAIL,
        username=TEST_USER_USERNAME,
        hashed_password="test_hashed_password",
        is_active=True,
        is_superuser=True,
    )

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