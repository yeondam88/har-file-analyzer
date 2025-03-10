import logging

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
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise 