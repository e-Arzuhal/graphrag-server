"""
Tests for contract API endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from app.main import app
from app.models.response.contract import ClauseDTO, ContractTemplateResponse
from app.services.exceptions import ContractNotFoundError


@pytest.fixture
def mock_contract_data():
    """Sample contract data for testing."""
    return {
        "display_name": "Borç Sözleşmesi",
        "clauses": [
            {"id": "clause_001", "template": "Test template 1", "necessity": "mandatory"},
            {"id": "clause_002", "template": "Test template 2", "necessity": "optional"},
        ]
    }


@pytest.fixture
def mock_contract_types():
    """Sample contract types for testing."""
    return [
        {"name": "borc_sozlesmesi", "display_name": "Borç Sözleşmesi"},
        {"name": "kira_sozlesmesi", "display_name": "Kira Sözleşmesi"},
    ]


class TestContractEndpoints:
    """Test suite for contract API endpoints."""

    @pytest.mark.asyncio
    async def test_get_contract_template_success(self, mock_contract_data):
        """Test successful retrieval of contract template."""
        with patch("app.api.routes.contract.get_contract_service") as mock_service:
            # Setup mock
            service_instance = MagicMock()
            service_instance.get_contract_template.return_value = ContractTemplateResponse(
                contract_type="borc_sozlesmesi",
                display_name=mock_contract_data["display_name"],
                clauses=[
                    ClauseDTO(**clause) for clause in mock_contract_data["clauses"]
                ]
            )
            mock_service.return_value = service_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/template/borc_sozlesmesi")
            
            assert response.status_code == 200
            data = response.json()
            assert data["contract_type"] == "borc_sozlesmesi"
            assert data["display_name"] == "Borç Sözleşmesi"
            assert len(data["clauses"]) == 2

    @pytest.mark.asyncio
    async def test_get_contract_template_not_found(self):
        """Test 404 response when contract type doesn't exist."""
        with patch("app.api.routes.contract.get_contract_service") as mock_service:
            service_instance = MagicMock()
            service_instance.get_contract_template.side_effect = ContractNotFoundError(
                "unknown_type"
            )
            mock_service.return_value = service_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/template/unknown_type")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_contract_types(self, mock_contract_types):
        """Test listing all contract types."""
        with patch("app.api.routes.contract.get_contract_service") as mock_service:
            service_instance = MagicMock()
            service_instance.get_all_contract_types.return_value = mock_contract_types
            mock_service.return_value = service_instance

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/template/")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["name"] == "borc_sozlesmesi"


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test root endpoint returns healthy status."""
        with patch("app.main.neo4j_driver"):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/")
            
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
