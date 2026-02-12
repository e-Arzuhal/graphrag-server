"""
API routes package.
Contains all FastAPI router modules.
"""
from app.api.routes.contract import router as contract_router
from app.api.routes.graphrag import router as graphrag_router

__all__ = ["contract_router", "graphrag_router"]
