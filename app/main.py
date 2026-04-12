"""
e-Arzuhal GraphRAG Server — main.py
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.utils.db import neo4j_driver
from app.api.routes.graphrag import router as graphrag_router
from app.api.routes.legal_analysis import router as legal_analysis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        neo4j_driver.connect()
        print("✓ Neo4j connection established successfully")
    except Exception as e:
        print(f"✗ Failed to connect to Neo4j: {e}")
        raise
    yield
    neo4j_driver.close()
    print("✓ Neo4j connection closed")


settings = get_settings()

_debug = os.getenv("DEBUG", "true").lower() == "true"
_internal_api_key = os.getenv("INTERNAL_API_KEY", "")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs"    if _debug else None,
    redoc_url="/redoc"  if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

# CORS — yalnızca main-server erişmeli
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Internal API key kontrolü. INTERNAL_API_KEY set edilmemişse (dev) pas geçer."""
    if request.url.path in ("/health", "/"):
        return await call_next(request)
    if _internal_api_key and request.headers.get("X-Internal-API-Key") != _internal_api_key:
        return JSONResponse(status_code=401, content={"detail": "Geçersiz veya eksik API anahtarı"})
    return await call_next(request)

# Routers
app.include_router(graphrag_router,       prefix="/api/v1")
app.include_router(legal_analysis_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    return {"status": "healthy", "message": "e-Arzuhal GraphRAG Server is running"}


@app.get("/health", tags=["Health"])
async def health_check():
    try:
        with neo4j_driver.get_session() as session:
            session.run("RETURN 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "components": {"server": "running", "neo4j": db_status},
        "version": settings.app_version,
    }
