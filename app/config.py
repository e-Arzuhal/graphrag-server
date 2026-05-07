"""
Application configuration module.
Loads settings from environment variables using pydantic-settings.
"""
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings

# Resolve .env relative to this file's location (project root)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        neo4j_uri: The connection URI for Neo4j database (e.g., bolt://localhost:7687)
        neo4j_user: Neo4j database username
        neo4j_password: Neo4j database password
        app_name: Application name for FastAPI
        app_version: Application version
        debug: Debug mode flag
        internal_api_key: The internal API key for securing communications
    """
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    app_name: str = "e-Arzuhal GraphRAG API"
    app_version: str = "1.0.0"
    debug: bool = False
    internal_api_key: str
    # Birincil Gemini API anahtarı; quota / 503 / boş yanıt durumunda
    # gemini_api_key_fallback'e otomatik geçilir.
    gemini_api_key: str = ""
    gemini_api_key_fallback: str = ""

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    Uses lru_cache to avoid re-reading environment variables on each call.
    
    Returns:
        Settings: Application configuration instance
    """
    return Settings()
