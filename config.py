from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pathlib import Path
from typing import Optional, List, Any
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Security
    secret_key: str = "dev_secret_key_123"
    csrf_secret_key: str = "dev_csrf_key_123"
    admin_password: str = "admin123"
    
    # Telegram Bot
    bot_token: str = "7490482214:AAGw84na2tfbHvo3onjSlTyjIzQLxIlwyzI"
    
    # Azure OpenAI
    azure_openai_api_key: str = "1NQqBkBk0psCS1ZttrbX9TJx...CHYHv6XJ3w3AAAAACOGk75G"
    azure_openai_endpoint: str = "https://kitep-mbg8rzqy-e....services.ai.azure.com/"
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_api_version: str = "2024-11-20"
    
    # File paths
    base_dir: Path = Path(__file__).parent
    data_dir: Path = base_dir / "data"
    upload_dir: Path = base_dir / "frontend/static/uploads"
    
    # File limits
    max_upload_size: int = 5 * 1024 * 1024  # 5MB
    allowed_extensions: set = {"jpg", "jpeg", "png", "pdf"}
    
    # Session
    session_cookie_name: str = "session"
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = "Lax"
    session_expire_minutes: int = 30
    
    # CORS
    cors_origins: List[str] = ["http://localhost:8000"]
    
    # Database
    database_url: str = "sqlite:///./test.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = ""
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Convert string CORS origins to list if needed
        if isinstance(self.cors_origins, str):
            try:
                self.cors_origins = json.loads(self.cors_origins)
            except json.JSONDecodeError:
                self.cors_origins = [self.cors_origins]

@lru_cache()
def get_settings() -> Settings:
    try:
        settings = Settings()
        logger.info("Settings loaded successfully")
        logger.info(f"Environment file path: {Path(__file__).parent / '.env'}")
        logger.info(f"Current working directory: {os.getcwd()}")
        return settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        raise

# Create required directories
try:
    settings = get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info("Directories created successfully")
except Exception as e:
    logger.error(f"Error creating directories: {e}")
    raise 