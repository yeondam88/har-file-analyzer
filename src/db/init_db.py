import logging
import os
import stat
import sqlite3
import sys
import time
import traceback
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.base import Base
from src.db.session import engine
from src.models import har_file, api_call, user  # Import all models so they are registered with the Base

# Configure root logger to show more detailed information
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Maximum retry attempts for database initialization
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds

def diagnose_sqlite_issue(db_path: str) -> Dict[str, Any]:
    """
    Diagnose SQLite issues by checking permissions, directory structure, etc.
    Returns a dictionary with diagnostic information.
    """
    diagnosis = {}
    
    try:
        # Path information
        diagnosis['path'] = db_path
        diagnosis['exists'] = os.path.exists(db_path)
        diagnosis['is_file'] = os.path.isfile(db_path) if diagnosis['exists'] else False
        
        # Directory information
        db_dir = os.path.dirname(db_path)
        diagnosis['directory'] = db_dir
        diagnosis['dir_exists'] = os.path.exists(db_dir)
        diagnosis['dir_is_dir'] = os.path.isdir(db_dir) if diagnosis['dir_exists'] else False
        
        # Permissions
        if diagnosis['dir_exists']:
            dir_stat = os.stat(db_dir)
            diagnosis['dir_mode'] = f"{dir_stat.st_mode:o}"
            diagnosis['dir_uid'] = dir_stat.st_uid
            diagnosis['dir_gid'] = dir_stat.st_gid
            
        if diagnosis['exists']:
            file_stat = os.stat(db_path)
            diagnosis['file_mode'] = f"{file_stat.st_mode:o}"
            diagnosis['file_uid'] = file_stat.st_uid
            diagnosis['file_gid'] = file_stat.st_gid
        
        # Process information
        diagnosis['process_uid'] = os.getuid()
        diagnosis['process_gid'] = os.getgid()
        diagnosis['process_euid'] = os.geteuid()
        diagnosis['process_egid'] = os.getegid()
        
        # File system information
        try:
            # Try to create a temporary file in the database directory
            with tempfile.NamedTemporaryFile(dir=db_dir, prefix='test_', suffix='.tmp', delete=True) as tmp:
                diagnosis['dir_writable'] = True
                diagnosis['temp_file_path'] = tmp.name
        except Exception as e:
            diagnosis['dir_writable'] = False
            diagnosis['dir_write_error'] = str(e)
        
        # Test SQLite directly
        try:
            # Try to create a test connection
            test_conn = sqlite3.connect(db_path)
            diagnosis['sqlite_connect'] = True
            
            # Try to create a test table
            try:
                test_conn.execute("CREATE TABLE IF NOT EXISTS diagnostic_test (id INTEGER PRIMARY KEY)")
                test_conn.execute("INSERT INTO diagnostic_test VALUES (1)")
                test_conn.commit()
                diagnosis['sqlite_write'] = True
            except Exception as write_err:
                diagnosis['sqlite_write'] = False
                diagnosis['sqlite_write_error'] = str(write_err)
            
            test_conn.close()
        except Exception as conn_err:
            diagnosis['sqlite_connect'] = False
            diagnosis['sqlite_connect_error'] = str(conn_err)
    
    except Exception as e:
        diagnosis['error'] = str(e)
        diagnosis['traceback'] = traceback.format_exc()
    
    return diagnosis

def try_fix_sqlite_permissions(db_path: str, in_coolify: bool = False) -> bool:
    """
    Attempt to fix SQLite database permissions.
    Returns True if successful, False otherwise.
    """
    try:
        db_dir = os.path.dirname(db_path)
        
        # Create directory with permissive permissions if it doesn't exist
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            os.chmod(db_dir, 0o777)  # Maximum permissions
            logger.info(f"Created directory with full permissions: {db_dir}")
        else:
            # Set permissive permissions on existing directory
            try:
                os.chmod(db_dir, 0o777)
                logger.info(f"Set full permissions on directory: {db_dir}")
            except Exception as dir_err:
                logger.warning(f"Could not set permissions on directory: {str(dir_err)}")
        
        # Check for WAL and SHM files and fix their permissions if they exist
        for ext in ['-wal', '-shm']:
            wal_file = f"{db_path}{ext}"
            if os.path.exists(wal_file):
                try:
                    os.chmod(wal_file, 0o666)
                    logger.info(f"Set permissions on {wal_file}")
                except Exception as wal_err:
                    logger.warning(f"Could not set permissions on {wal_file}: {str(wal_err)}")
        
        # Create or fix permissions on the database file
        if os.path.exists(db_path):
            try:
                os.chmod(db_path, 0o666)  # Make file readable/writable by everyone
                logger.info(f"Set rw permissions on database file: {db_path}")
            except Exception as file_err:
                logger.warning(f"Could not set permissions on file: {str(file_err)}")
        else:
            # Try to create an empty database file with the right permissions
            try:
                with open(db_path, 'w') as f:
                    pass
                os.chmod(db_path, 0o666)
                logger.info(f"Created empty database file with rw permissions: {db_path}")
            except Exception as create_err:
                logger.warning(f"Could not create database file: {str(create_err)}")
        
        # In Coolify, we might need more drastic measures
        if in_coolify:
            # Try using OS-level commands for more force
            os.system(f"mkdir -p {db_dir}")
            os.system(f"chmod -R 777 {db_dir}")
            if os.path.exists(db_path):
                os.system(f"chmod 666 {db_path}")
            else:
                os.system(f"touch {db_path}")
                os.system(f"chmod 666 {db_path}")
            
            # Also fix WAL and SHM files
            os.system(f"[ -f {db_path}-wal ] && chmod 666 {db_path}-wal || true")
            os.system(f"[ -f {db_path}-shm ] && chmod 666 {db_path}-shm || true")
            
            logger.info("Applied Coolify-specific fixes using system commands")
        
        # Test if fixes worked by trying to connect with a timeout
        test_conn = sqlite3.connect(db_path, timeout=10)
        test_conn.execute("PRAGMA busy_timeout=5000")  # 5 second timeout for locked operations
        test_conn.execute("CREATE TABLE IF NOT EXISTS permission_test (id INTEGER PRIMARY KEY)")
        test_conn.execute("INSERT INTO permission_test VALUES (1)")
        test_conn.commit()
        test_conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Failed to fix permissions: {str(e)}")
        return False

def init_db() -> None:
    """
    Initialize the database by creating all tables with robust error handling.
    """
    retry_count = 0
    db_path = None
    in_coolify = os.environ.get('IN_COOLIFY', 'false').lower() == 'true'
    
    logger.info(f"Starting database initialization (attempt 1/{MAX_RETRIES})...")
    logger.info(f"Environment: {'Coolify' if in_coolify else 'Standard'}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"User/Group: {os.getuid()}:{os.getgid()}")
    
    while retry_count < MAX_RETRIES:
        try:
            # Get the database URL from settings
            db_url = settings.DATABASE_URL
            logger.info(f"Database URL: {db_url}")
            
            # For SQLite databases
            if db_url.startswith('sqlite:///'):
                # Extract the database path from the URL
                if db_url.startswith('sqlite:////'):  # Absolute path (4 slashes)
                    db_path = db_url.replace('sqlite:////', '/')
                else:  # Relative path (3 slashes)
                    db_path = db_url.replace('sqlite:///', '')
                
                # Convert to absolute path if needed
                if not os.path.isabs(db_path):
                    db_path = os.path.abspath(db_path)
                
                logger.info(f"SQLite database path: {db_path}")
                
                # Make sure the database directory exists
                db_dir = os.path.dirname(db_path)
                
                # Try to create/fix permissions on the database
                try:
                    fix_result = try_fix_sqlite_permissions(db_path, in_coolify)
                    logger.info(f"Permission fix {'succeeded' if fix_result else 'failed'}")
                except Exception as fix_err:
                    logger.error(f"Error during permission fixing: {str(fix_err)}")
                
                # Special handling for Coolify environment
                if in_coolify:
                    logger.info("Applying special handling for Coolify environment")
                    
                    # Run diagnostics
                    diagnosis = diagnose_sqlite_issue(db_path)
                    logger.info(f"SQLite diagnosis: {diagnosis}")
                    
                    # Check if we can write to the database
                    try:
                        test_conn = sqlite3.connect(db_path)
                        test_conn.execute("CREATE TABLE IF NOT EXISTS coolify_test (id INTEGER PRIMARY KEY)")
                        test_conn.execute("INSERT INTO coolify_test VALUES (1)")
                        test_conn.commit()
                        test_conn.close()
                        logger.info(f"Successfully tested direct SQLite access")
                    except Exception as sqlite_err:
                        logger.error(f"Direct SQLite test failed: {str(sqlite_err)}")
                        
                        # If direct access fails, try one more fix before giving up
                        if not try_fix_sqlite_permissions(db_path, in_coolify=True):
                            # If we still can't access the database, raise the error to retry
                            raise RuntimeError(f"Cannot access SQLite database after fixing permissions: {str(sqlite_err)}")
            
            # Create all tables
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully.")
            
            # Success! Break out of the retry loop
            return
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Error initializing database (attempt {retry_count}/{MAX_RETRIES}): {str(e)}")
            logger.error(traceback.format_exc())
            
            # If there was a database file issue, run diagnostics
            if db_path:
                logger.info("Running SQLite diagnostics...")
                diagnosis = diagnose_sqlite_issue(db_path)
                logger.info(f"Diagnostic results: {diagnosis}")
            
            if retry_count < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to initialize database after {MAX_RETRIES} attempts")
                
                # Print to stderr as well for Coolify logs
                print(f"DATABASE INITIALIZATION FAILED after {MAX_RETRIES} attempts: {str(e)}", file=sys.stderr)
                
                # On final failure in Coolify, we could try to use an in-memory database as last resort
                if in_coolify and db_url.startswith('sqlite:///'):
                    logger.warning("FALLING BACK to in-memory SQLite database as last resort")
                    try:
                        # Override global engine with in-memory SQLite
                        from sqlalchemy import create_engine
                        
                        # Create new in-memory engine
                        memory_engine = create_engine(
                            "sqlite:///:memory:",
                            connect_args={"check_same_thread": False}
                        )
                        
                        # Override the global engine
                        globals()['engine'] = memory_engine
                        
                        # Create tables in memory
                        Base.metadata.create_all(bind=memory_engine)
                        
                        logger.warning("Successfully initialized in-memory database as fallback")
                        
                        # Don't raise the exception since we've recovered
                        return
                    except Exception as mem_err:
                        logger.error(f"Failed to initialize in-memory database: {str(mem_err)}")
                
                # Re-raise the last exception if we couldn't handle it
                raise 