"""
e-Arzuhal GraphRAG Server

A Retrieval-Augmented Generation (RAG) server for legal document generation
using a Neo4j Knowledge Graph.

This server provides API endpoints to retrieve contract template structures
based on contract types. It acts as an intermediary between NLP services
and a knowledge graph containing legal document templates.

Main Features:
- Retrieve contract templates with mandatory and optional clauses
- Query a Neo4j knowledge graph for legal document structures
- Support for multiple contract types

Usage:
    uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.utils.db import neo4j_driver
from app.api.routes.contract import router as contract_router
from app.api.routes.graphrag import router as graphrag_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    Startup:
        - Initializes the Neo4j driver connection
        - Verifies database connectivity
    
    Shutdown:
        - Closes the Neo4j driver connection gracefully
    
    Args:
        app: The FastAPI application instance
    """
    # Startup: Connect to Neo4j
    try:
        neo4j_driver.connect()
        print("✓ Neo4j connection established successfully")
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {e}")
        raise
    
    yield  # Application runs here
    
    # Shutdown: Close Neo4j connection
    neo4j_driver.close()
    print("✓ Neo4j connection closed")


# Get application settings
settings = get_settings()

# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## e-Arzuhal GraphRAG API
    
    This API provides access to legal document templates stored in a Neo4j knowledge graph.
    
    ### Features:
    - **Contract Templates**: Retrieve full contract structures with clauses
    - **Knowledge Graph**: Query relationships between contract types and clauses
    - **RAG Integration**: Designed for integration with NLP/LLM services
    
    ### Graph Schema:
    - **Nodes**: `ContractType`, `Clause`
    - **Relationships**: `REQUIRES` (mandatory), `INCLUDES` (optional)
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(contract_router, prefix="/api/v1")
app.include_router(graphrag_router, prefix="/api/v1")


@app.get(
    "/",
    tags=["Health"],
    summary="Health Check",
    description="Check if the GraphRAG server is running"
)
async def root():
    """
    Root endpoint for health checking.
    
    Returns:
        dict: Server status message
    """
    return {
        "status": "healthy",
        "message": "e-Arzuhal GraphRAG Server is running",
        "version": settings.app_version
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Detailed Health Check",
    description="Check server health including database connectivity"
)
async def health_check():
    """
    Detailed health check endpoint.
    
    Verifies:
    - Server is running
    - Neo4j database is accessible
    
    Returns:
        dict: Detailed health status
    """
    try:
        # Test database connectivity
        with neo4j_driver.get_session() as session:
            session.run("RETURN 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "components": {
            "server": "running",
            "neo4j": db_status
        },
        "version": settings.app_version
    }
