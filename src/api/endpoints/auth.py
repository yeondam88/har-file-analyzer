from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_active_user, TEST_USER_ID, TEST_USER_EMAIL, TEST_USER_USERNAME
from src.core.config import settings
from src.core.security import create_access_token, get_password_hash, verify_password
from src.db.session import get_db
from src.models.user import User
from src.schemas.user import Token, User as UserSchema, UserCreate

router = APIRouter()


@router.post("/login", response_model=Token)
def login_access_token(
    # db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Test version: OAuth2 compatible token login, returns a test token without authentication.
    """
    # Original login logic commented out for testing
    """
    # Find the user by username
    user = db.query(User).filter(User.username == form_data.username).first()
    
    # Check if user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.id, expires_delta=access_token_expires)
    """
    
    # For testing, return a dummy token
    return {"access_token": "test_token", "token_type": "bearer"}


@router.post("/register", response_model=UserSchema)
def register_user(
    # *, db: Session = Depends(get_db), user_in: UserCreate
) -> Any:
    """
    Test version: Register a new user, returns a test user without database interaction.
    """
    # Original registration logic commented out for testing
    """
    # Check if username already exists
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Check if email already exists
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create new user
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user
    """
    
    # For testing, return a dummy user
    return {
        "id": TEST_USER_ID,
        "email": TEST_USER_EMAIL,
        "username": TEST_USER_USERNAME,
        "is_active": True,
        "is_superuser": True,
        "created_at": "2025-03-09T12:00:00",
        "updated_at": "2025-03-09T12:00:00"
    }


@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_active_user)) -> Any:
    """
    Get current user.
    """
    return current_user


@router.get("/health")
def health_check() -> Any:
    """
    Health check endpoint.
    """
    return {"status": "ok"} 