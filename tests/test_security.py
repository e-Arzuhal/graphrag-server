"""
Security regression tests for graphrag-server.

Patches module-level _internal_api_key / _debug in app.main so no .env is needed.
Neo4j is not required — endpoints that need DB are not hit for auth-path tests.
"""
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

import app.main as graphrag_main
from app.main import app

VALID_KEY = "test-secret-key-32-chars-min-ok!"
ANALYZE_PAYLOAD = {
    "contract_type": "kira_sozlesmesi",
    "extracted_entities": {
        "PERSON": [], "ORG": [], "LOC": [],
        "MONEY": [], "DATE": [], "CARDINAL": [], "PERCENT": [],
    },
}


class TestApiKeyEnforcement:

    @pytest.mark.asyncio
    async def test_wrong_key_returns_401(self):
        """Yanlış API anahtarı → 401."""
        with patch.object(graphrag_main, "_internal_api_key", VALID_KEY), \
             patch.object(graphrag_main, "_debug", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/analyze/input",
                    json=ANALYZE_PAYLOAD,
                    headers={"X-Internal-API-Key": "yanlis-anahtar"},
                )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self):
        """Header eksikse → 401."""
        with patch.object(graphrag_main, "_internal_api_key", VALID_KEY), \
             patch.object(graphrag_main, "_debug", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/analyze/input", json=ANALYZE_PAYLOAD)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_key_debug_false_returns_503(self):
        """INTERNAL_API_KEY boş + DEBUG=false → 503."""
        with patch.object(graphrag_main, "_internal_api_key", ""), \
             patch.object(graphrag_main, "_debug", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/analyze/input", json=ANALYZE_PAYLOAD)
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_no_key_debug_true_passes_through(self):
        """INTERNAL_API_KEY boş + DEBUG=true → geçişe izin verilir (401/503 değil)."""
        with patch.object(graphrag_main, "_internal_api_key", ""), \
             patch.object(graphrag_main, "_debug", True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/analyze/input", json=ANALYZE_PAYLOAD)
        assert response.status_code not in (401, 503)

    @pytest.mark.asyncio
    async def test_correct_key_returns_not_401(self):
        """Doğru API anahtarı ile istek → 401 değil."""
        with patch.object(graphrag_main, "_internal_api_key", VALID_KEY), \
             patch.object(graphrag_main, "_debug", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/analyze/input",
                    json=ANALYZE_PAYLOAD,
                    headers={"X-Internal-API-Key": VALID_KEY},
                )
        assert response.status_code != 401


class TestHealthBypass:

    @pytest.mark.asyncio
    async def test_health_endpoint_bypasses_api_key(self):
        """/health API anahtarı olmadan erişilebilir olmalı."""
        with patch.object(graphrag_main, "_internal_api_key", VALID_KEY), \
             patch.object(graphrag_main, "_debug", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/health")
        assert response.status_code == 200


class TestSwaggerExposure:

    @pytest.mark.asyncio
    async def test_openapi_hidden_when_debug_false(self):
        """/openapi.json → DEBUG=false iken 404 (Swagger kapalı)."""
        with patch.object(graphrag_main, "_debug", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/openapi.json")
        assert response.status_code in (404, 403)
