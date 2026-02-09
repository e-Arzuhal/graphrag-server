"""
Application configuration module.
Loads settings from environment variables using pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


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
    """
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    app_name: str = "e-Arzuhal GraphRAG API"
    app_version: str = "1.0.0"
    debug: bool = False

    class Config:
        env_file = ".env"
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
