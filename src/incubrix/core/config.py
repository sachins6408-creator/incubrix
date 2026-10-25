import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "IncuBrix"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOADS_DIR: Path = DATA_DIR / "storage" / "uploads"
    RENDERS_DIR: Path = DATA_DIR / "storage" / "renders"
    DB_PATH: Path = DATA_DIR / "db" / "incubrix.db"
    STATIC_DIR: Path = BASE_DIR / "static"
    
    # Binaries
    FFMPEG_PATH: str = os.environ.get("FFMPEG_PATH", str(BASE_DIR / "bin" / "ffmpeg.exe"))
    FFPROBE_PATH: str = os.environ.get("FFPROBE_PATH", str(BASE_DIR / "bin" / "ffprobe.exe"))
    
    # Upload limits
    MAX_UPLOAD_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MB
    ALLOWED_EXTENSIONS: list[str] = [".mp4", ".mov", ".mkv", ".avi", ".webm"]
    
    # Engine Settings
    ENGINE_MODE: str = "Local deterministic instruction engine"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure directories exist
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.RENDERS_DIR.mkdir(parents=True, exist_ok=True)
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
