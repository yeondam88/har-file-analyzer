#!/usr/bin/env python3
import sys
import os
import argparse
from getpass import getpass

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.models.user import User
from src.core.security import get_password_hash


def create_superuser(username: str, email: str, password: str) -> None:
    """
    Create a superuser in the database.
    """
    db = SessionLocal()
    
    try:
        # Check if user already exists
        user = db.query(User).filter(User.username == username).first()
        if user:
            print(f"User with username '{username}' already exists.")
            return
        
        # Check if email already exists
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User with email '{email}' already exists.")
            return
        
        # Create superuser
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=True,
        )
        
        db.add(user)
        db.commit()
        
        print(f"Superuser '{username}' created successfully.")
    
    except Exception as e:
        db.rollback()
        print(f"Error creating superuser: {str(e)}")
    
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a superuser for HAR File Analyzer")
    parser.add_argument("--username", help="Superuser username")
    parser.add_argument("--email", help="Superuser email")
    parser.add_argument("--password", help="Superuser password")
    
    args = parser.parse_args()
    
    username = args.username
    if not username:
        username = input("Enter username: ")
    
    email = args.email
    if not email:
        email = input("Enter email: ")
    
    password = args.password
    if not password:
        password = getpass("Enter password: ")
        password_confirm = getpass("Confirm password: ")
        
        if password != password_confirm:
            print("Passwords do not match.")
            sys.exit(1)
    
    create_superuser(username, email, password) 