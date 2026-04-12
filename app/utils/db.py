"""
Neo4j database driver utility module.
Provides a singleton pattern for managing Neo4j driver connections.
"""
from typing import Optional
from neo4j import GraphDatabase, Driver

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class Neo4jDriver:
    """
    Singleton class to manage the Neo4j Driver connection.
    
    This class ensures only one driver instance exists throughout the application
    lifecycle, preventing connection pool exhaustion and resource leaks.
    
    Usage:
        # Get the singleton instance
        db = Neo4jDriver()
        
        # Connect to database (typically at app startup)
        db.connect()
        
        # Get session for queries
        with db.get_session() as session:
            result = session.run("MATCH (n) RETURN n LIMIT 10")
        
        # Close connection (typically at app shutdown)
        db.close()
    """
    
    _instance: Optional["Neo4jDriver"] = None
    _driver: Optional[Driver] = None

    def __new__(cls) -> "Neo4jDriver":
        """
        Create a new instance only if one doesn't exist (Singleton pattern).
        
        Returns:
            Neo4jDriver: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> None:
        """
        Establish connection to Neo4j database.
        
        Reads connection parameters from environment variables:
        - NEO4J_URI: Database URI (e.g., bolt://localhost:7687)
        - NEO4J_USER: Database username
        - NEO4J_PASSWORD: Database password
        
        Raises:
            Exception: If connection fails
        """
        if self._driver is None:
            settings = get_settings()
            logger.info("Connecting to Neo4j at %s as %s", settings.neo4j_uri, settings.neo4j_user)
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            logger.info("Neo4j driver verified")

    def close(self) -> None:
        """
        Close the Neo4j driver connection.
        Should be called during application shutdown.
        """
        if self._driver is not None:
            logger.debug("Closing Neo4j driver")
            self._driver.close()
            self._driver = None

    def get_driver(self) -> Driver:
        """
        Get the Neo4j driver instance.
        
        Returns:
            Driver: The Neo4j driver instance
            
        Raises:
            RuntimeError: If driver is not connected
        """
        if self._driver is None:
            raise RuntimeError(
                "Neo4j driver is not connected. Call connect() first."
            )
        return self._driver

    def get_session(self):
        """
        Get a new Neo4j session.
        
        Returns:
            Session: A new Neo4j session for executing queries
            
        Raises:
            RuntimeError: If driver is not connected
        """
        return self.get_driver().session()


# Global instance for easy access
neo4j_driver = Neo4jDriver()


def get_neo4j_driver() -> Neo4jDriver:
    """
    Dependency injection helper for FastAPI.
    
    Returns:
        Neo4jDriver: The singleton Neo4j driver instance
    """
    return neo4j_driver
