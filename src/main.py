import logging
from pathlib import Path
import os

from fastapi import FastAPI, APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.exceptions import RequestValidationError

from src.api.router import api_router
from src.core.config import settings
from src.core.exceptions import HARFileException
from src.db.init_db import init_db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """
    Create the FastAPI application.
    """
    # Initialize FastAPI app
    application = FastAPI(
        title=settings.APP_NAME,
        description="A tool for parsing HAR files to extract and replay API calls",
        debug=settings.DEBUG,
        version="0.1.0",
    )
    
    # Configure CORS - Proper configuration following best practices
    logger.info(f"Configuring CORS with allowed origins: {settings.CORS_ORIGINS}")
    # Debug for CORS origins
    logger.info(f"CORS_ORIGINS from environment: {os.environ.get('CORS_ORIGINS', 'Not set')}")
    
    # Ensure CORS_ORIGINS is a list and has valid values
    cors_origins = settings.CORS_ORIGINS
    if not isinstance(cors_origins, list):
        logger.warning(f"CORS_ORIGINS is not a list, converting: {cors_origins}")
        if isinstance(cors_origins, str):
            cors_origins = [cors_origins]
        else:
            logger.error(f"Invalid CORS_ORIGINS type: {type(cors_origins)}")
            cors_origins = ["http://localhost:3000"]
    
    logger.info(f"Final CORS origins configuration: {cors_origins}")
    
    application.add_middleware(
        CORSMiddleware,
        # Explicitly list allowed origins - don't use wildcard with credentials
        allow_origins=cors_origins,
        # Only set to True if you need cookies or auth headers
        allow_credentials=False,
        # Specify exact methods for better security
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        # Specify exact headers for better security
        allow_headers=["Content-Type", "Authorization", "Accept"],
        # Expose these headers to the frontend
        expose_headers=["Content-Type", "Content-Length"],
        # Cache preflight requests for 1 hour
        max_age=3600,
    )
    
    # Include API router
    application.include_router(api_router, prefix="/api")
    
    # Add middleware to log request origins for CORS debugging
    @application.middleware("http")
    async def log_request_origin(request: Request, call_next):
        origin = request.headers.get("origin", "No origin header")
        logger.info(f"Request received from origin: {origin}, path: {request.url.path}")
        response = await call_next(request)
        return response
    
    # Debug endpoint to check CORS settings
    @application.get("/debug/cors", include_in_schema=False)
    async def debug_cors():
        """Endpoint to debug CORS settings"""
        return {
            "cors": "enabled",
            "message": "CORS is working correctly",
            "debug_info": {
                "allowed_origins": settings.CORS_ORIGINS,
                "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                "allow_headers": ["Content-Type", "Authorization", "Accept"]
            },
            "environment_variables": {
                "CORS_ORIGINS_ENV": os.environ.get("CORS_ORIGINS", "Not set in environment"),
                "raw_env_keys": list(os.environ.keys())
            },
            "settings_dump": {
                "app_name": settings.APP_NAME,
                "debug_mode": settings.DEBUG,
                "allowed_hosts": settings.ALLOWED_HOSTS
            }
        }
    
    # Add exception handlers
    @application.exception_handler(HARFileException)
    async def har_exception_handler(request: Request, exc: HARFileException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )
    
    return application


app = create_application()


@app.on_event("startup")
async def startup_event():
    """
    Initialize the application on startup.
    """
    logger.info("Initializing the database...")
    init_db()
    logger.info("Database initialized successfully.")


@app.get("/", include_in_schema=False)
async def root():
    """
    Root endpoint, redirects to docs.
    """
    return {"message": "Welcome to HAR File Analyzer API. See /docs for API documentation."} 