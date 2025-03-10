from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import os
import time
import sqlite3
import logging

from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum number of retries for database connection
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds

# Determine if running in Coolify environment
IN_COOLIFY = os.environ.get('IN_COOLIFY', 'false').lower() == 'true'

def get_engine():
    """
    Create SQLAlchemy engine with error handling and retry logic
    """
    retry_count = 0
    last_error = None
    
    while retry_count < MAX_RETRIES:
        try:
            logger.info(f"Attempting to connect to database at {settings.DATABASE_URL}")
            
            # Parse the database URL to extract the path for SQLite
            if settings.DATABASE_URL.startswith('sqlite'):
                db_path = settings.DATABASE_URL.replace('sqlite:///', '')
                
                # For absolute paths that start with /
                if db_path.startswith('/'):
                    db_path = db_path
                else:
                    # For relative paths, ensure they're relative to the current directory
                    db_path = os.path.join(os.getcwd(), db_path)
                    
                db_dir = os.path.dirname(db_path)
                
                # Ensure the directory exists
                if not os.path.exists(db_dir):
                    logger.info(f"Creating database directory: {db_dir}")
                    os.makedirs(db_dir, exist_ok=True)
                
                # Try to create/open the database file directly with sqlite3
                try:
                    logger.info(f"Testing direct SQLite access to {db_path}")
                    conn = sqlite3.connect(db_path)
                    conn.execute("CREATE TABLE IF NOT EXISTS connection_test (id INTEGER PRIMARY KEY)")
                    conn.commit()
                    conn.close()
                    logger.info("Direct SQLite connection test successful")
                except Exception as e:
                    logger.error(f"Direct SQLite connection test failed: {str(e)}")
                    if IN_COOLIFY:
                        # In Coolify, try setting more permissive permissions
                        try:
                            logger.info("Applying Coolify-specific fixes...")
                            os.system(f"chmod 777 {db_dir}")
                            if os.path.exists(db_path):
                                os.system(f"chmod 666 {db_path}")
                            logger.info("Applied permissions fix in Coolify environment")
                        except Exception as perm_err:
                            logger.error(f"Failed to fix permissions: {str(perm_err)}")
            
            # For SQLite, add event listeners to enable foreign keys
            if settings.DATABASE_URL.startswith("sqlite"):
                @event.listens_for(engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA journal_mode=WAL")
                    # Increase timeout to reduce locking issues
                    cursor.execute("PRAGMA busy_timeout=10000")
                    # Set recommended settings for concurrency
                    cursor.execute("PRAGMA temp_store=MEMORY")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA cache_size=10000")
                    cursor.close()
            
            # Create the engine with appropriate connect_args
            engine = create_engine(
                settings.DATABASE_URL,
                # For SQLite, enable foreign key constraints and set timeout
                connect_args={
                    "check_same_thread": False,
                    "timeout": 60,  # Increase timeout to 60 seconds (from 30)
                    "isolation_level": "IMMEDIATE",  # Helps with concurrent access
                } if settings.DATABASE_URL.startswith("sqlite") else {},
                # More resilient connection pool settings
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,  # Limit connection pool size
                max_overflow=10,  # Allow a few more connections if needed
            )
            
            # Test the engine by making a simple query
            with engine.connect() as conn:
                conn.execute("SELECT 1")
                logger.info("Database connection successful")
            
            return engine
            
        except Exception as e:
            last_error = e
            retry_count += 1
            logger.error(f"Database connection attempt {retry_count} failed: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to connect to database after {MAX_RETRIES} attempts")
                # Re-raise the last error if all retries failed
                raise
    
    # This should not be reached, but just in case
    raise last_error

# Create SQLAlchemy engine with retry logic
try:
    engine = get_engine()
    
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
except Exception as e:
    logger.error(f"Fatal error initializing database: {str(e)}")
    # Create an engine anyway to prevent startup errors, but it will fail on actual DB operations
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency function to get a database session.
    This will be used by FastAPI dependency injection system.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Error during database session: {str(e)}")
        raise
    finally:
        db.close() 