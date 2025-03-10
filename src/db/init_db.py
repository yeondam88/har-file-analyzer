import logging
import os
import stat
import sqlite3

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
            # Extract the database path from the URL
            if db_url.startswith('sqlite:////'):  # Absolute path (4 slashes)
                db_path = db_url.replace('sqlite:////', '/')
            else:  # Relative path (3 slashes)
                db_path = db_url.replace('sqlite:///', '')
            
            logger.info(f"Database path from URL: {db_path}")
            
            # Ensure the directory exists
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
                # Try to set explicit permissions to ensure the directory is writable
                try:
                    os.chmod(db_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777 permissions
                    logger.info(f"Set permissions on database directory: {db_dir}")
                except Exception as perm_err:
                    logger.warning(f"Could not set permissions on {db_dir}: {perm_err}")
                
                logger.info(f"Ensured database directory exists: {db_dir}")
                
                # Try to touch the database file to ensure it's creatable
                try:
                    # Test if we can write to the directory by creating an empty file
                    test_path = os.path.join(db_dir, "test_write_access.txt")
                    with open(test_path, 'w') as f:
                        f.write("test")
                    os.remove(test_path)
                    logger.info(f"Successfully verified write access to {db_dir}")
                except Exception as write_err:
                    logger.error(f"Cannot write to the database directory {db_dir}: {write_err}")
                    logger.error(f"Current directory: {os.getcwd()}")
                    logger.error(f"Directory contents: {os.listdir(db_dir) if os.path.exists(db_dir) else 'directory does not exist'}")
                    logger.error(f"Directory permissions: {os.stat(db_dir).st_mode if os.path.exists(db_dir) else 'N/A'}")
                    logger.error(f"User ID: {os.getuid()}, Group ID: {os.getgid()}")
            
            # Log if the database file already exists
            if os.path.exists(db_path):
                logger.info(f"Database file already exists at {db_path}")
                # Check if it's writable
                if os.access(db_path, os.W_OK):
                    logger.info(f"Database file is writable")
                else:
                    logger.warning(f"Database file exists but is not writable: {db_path}")
                    try:
                        os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
                        logger.info(f"Updated permissions on existing database file")
                    except Exception as file_perm_err:
                        logger.error(f"Failed to update permissions on database file: {file_perm_err}")
        
        # Test database connection with direct SQLite
        if db_url.startswith('sqlite:///'):
            try:
                db_path_for_sqlite = db_path
                logger.info(f"Testing direct SQLite connection to: {db_path_for_sqlite}")
                conn = sqlite3.connect(db_path_for_sqlite)
                conn.execute("SELECT 1")
                conn.close()
                logger.info("Direct SQLite connection successful")
            except Exception as sqlite_err:
                logger.error(f"Direct SQLite connection failed: {sqlite_err}")
        
        # Create all tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        # More detailed error information
        if db_url.startswith('sqlite:///'):
            logger.error(f"SQLite database path: {db_path}")
            logger.error(f"Current directory: {os.getcwd()}")
            logger.error(f"Directory exists: {os.path.exists(db_dir) if 'db_dir' in locals() else 'unknown'}")
            logger.error(f"Process user/group: {os.getuid()}:{os.getgid()}")
        raise 