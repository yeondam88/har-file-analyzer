import logging
from pathlib import Path

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
    application.add_middleware(
        CORSMiddleware,
        # Explicitly list allowed origins - don't use wildcard with credentials
        allow_origins=settings.CORS_ORIGINS,
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