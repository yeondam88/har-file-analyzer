from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from src.api.endpoints import auth, har_files, api_calls

api_router = APIRouter()

# Include routers from endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(har_files.router, prefix="/har-files", tags=["har-files"])
api_router.include_router(api_calls.router, prefix="/api-calls", tags=["api-calls"])

# Health check endpoint
@api_router.get("/health", tags=["health"])
def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}

# CORS preflight check endpoint
@api_router.options("/cors-check", tags=["debug"])
def cors_preflight_check():
    """
    CORS preflight check endpoint.
    This endpoint helps debug CORS issues by responding to OPTIONS requests.
    """
    response = JSONResponse(content={"cors": "enabled"})
    # Ensure these match the CORS middleware configuration
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept"
    response.headers["Access-Control-Max-Age"] = "3600"
    return response

# CORS check endpoint
@api_router.get("/cors-check", tags=["debug"])
def cors_check():
    """
    CORS check endpoint.
    This endpoint helps debug CORS issues by providing a test endpoint.
    """
    response = JSONResponse(content={
        "cors": "enabled", 
        "message": "CORS is working correctly",
        "debug_info": {
            "allowed_origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization", "Accept"],
        }
    })
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
    return response 