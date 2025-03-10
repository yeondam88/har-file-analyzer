import logging
import os

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.base import Base
from src.db.session import engine
from src.models import har_file, api_call, user  # Import all models so they are registered with the Base

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    """
    try:
        # Ensure database directory exists
        db_url = settings.DATABASE_URL
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            
            # Handle both absolute and relative paths
            if db_path.startswith('/'):
                # Absolute path
                db_dir = os.path.dirname(db_path)
            else:
                # Relative path
                if db_path.startswith('./'):
                    db_path = db_path[2:]
                db_dir = os.path.dirname(db_path)
                
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Ensured database directory exists: {db_dir}")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise 