"""
API routes package.
Contains all FastAPI router modules.
"""
from app.api.routes.contract import router as contract_router

__all__ = ["contract_router"]
