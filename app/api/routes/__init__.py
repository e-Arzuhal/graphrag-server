"""
API routes package.
Contains all FastAPI router modules.
"""
from app.api.routes.graphrag import router as graphrag_router

__all__ = ["graphrag_router"]
