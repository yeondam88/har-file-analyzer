import os
from typing import List, Optional, Union

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "HAR File Analyzer"
    DEBUG: bool = False
    SECRET_KEY: str
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]
    
    # Database
    DATABASE_URL: str
    
    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    # Use a string as the base type to avoid Pydantic trying to parse as JSON first
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Process the CORS_ORIGINS_STR into a list of allowed origins."""
        value = self.CORS_ORIGINS_STR
        # Handle comma-separated string
        if "," in value and not value.startswith("["):
            return [i.strip() for i in value.split(",")]
        # Handle JSON-formatted string
        elif value.startswith("[") and value.endswith("]"):
            try:
                import json
                return json.loads(value)
            except json.JSONDecodeError:
                # Fall back to treating as a single URL if JSON parsing fails
                return [value]
        # Handle single URL
        return [value]
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)


# Create settings instance
settings = Settings() 