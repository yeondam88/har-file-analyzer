import logging
from pathlib import Path
import os
import socket

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
    logger.info(f"CORS_ORIGINS_STR from environment: {os.environ.get('CORS_ORIGINS_STR', 'Not set')}")
    
    # Get the processed CORS origins list
    cors_origins = settings.CORS_ORIGINS
    
    # Ensure our specific domain is in the list
    specific_origin = "http://wkg08ks0g0cg40sk04gcscwo.5.78.133.23.sslip.io:3088"
    if specific_origin not in cors_origins:
        cors_origins.append(specific_origin)
    
    logger.info(f"Final CORS origins: {cors_origins}")
    
    # Add CORS middleware FIRST - order matters in FastAPI
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
        expose_headers=["Content-Type", "Content-Length"],
        max_age=3600,
    )
    
    # Add middleware to log request origins for CORS debugging
    @application.middleware("http")
    async def log_request_origin(request: Request, call_next):
        origin = request.headers.get("origin", "No origin header")
        logger.info(f"Request received from origin: {origin}, path: {request.url.path}")
        response = await call_next(request)
        # Log CORS headers in response for debugging
        logger.info(f"Response headers: {dict(response.headers)}")
        return response
    
    # Debug endpoint to check CORS settings
    @application.get("/debug/cors", include_in_schema=False)
    async def debug_cors(request: Request):
        """Endpoint to debug CORS settings"""
        # Get all request headers
        headers = {k: v for k, v in request.headers.items()}
        
        # Get local IP addresses
        host_name = socket.gethostname()
        host_ip = socket.gethostbyname(host_name)
        
        return {
            "cors": "enabled",
            "message": "CORS is working correctly",
            "request": {
                "client_host": request.client.host if request.client else None,
                "headers": headers,
                "url": str(request.url)
            },
            "server": {
                "hostname": host_name,
                "ip": host_ip
            },
            "debug_info": {
                "allowed_origins": cors_origins,
                "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With"],
                "allow_credentials": True,
                "configured_api_url": os.environ.get("NEXT_PUBLIC_API_URL", "Not set")
            },
            "environment_variables": {
                "CORS_ORIGINS_STR": os.environ.get("CORS_ORIGINS_STR", "Not set in environment"),
                "raw_env_keys": list(os.environ.keys())
            },
            "settings_dump": {
                "app_name": settings.APP_NAME,
                "debug_mode": settings.DEBUG,
                "allowed_hosts": settings.ALLOWED_HOSTS
            }
        }
    
    # Simple test endpoint for CORS
    @application.get("/api/test-cors", include_in_schema=False)
    async def test_cors():
        """Simple endpoint to test if CORS is working"""
        return {"message": "CORS is working if you can see this message"}
    
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
    
    # Include API router
    application.include_router(api_router, prefix="/api")
    
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