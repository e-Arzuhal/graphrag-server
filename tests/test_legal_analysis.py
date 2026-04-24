"""
Integration tests for /api/v1/legal-analysis/* endpoints.
Contract repository is mocked so Neo4j is not required.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app

MOCK_ARTICLES = [
    {
        "article_id": "TBK-299",
        "law_name": "Türk Borçlar Kanunu",
        "article_number": "Madde 299",
        "summary": "Kira sözleşmesinin tanımı.",
        "relevance_score": 1.0,
    }
]

MOCK_CONTRACT_GRAPH = {
    "nodes": [{"id": "kira_sozlesmesi", "type": "SOZLESME_TIPI", "name": "Kira Sözleşmesi"}],
    "relationships": [],
}


@pytest.fixture
def mock_repo():
    with patch("app.api.routes.legal_analysis.contract_repo") as mock:
        mock.get_related_articles = MagicMock(return_value=MOCK_ARTICLES)
        mock.get_contract_graph = MagicMock(return_value=MOCK_CONTRACT_GRAPH)
        yield mock


class TestLegalAnalysisEndpoint:

    @pytest.mark.asyncio
    async def test_contract_legal_analysis_returns_200(self, mock_repo):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/legal-analysis/contract-legal-analysis",
                json={
                    "contract_type": "kira_sozlesmesi",
                    "clauses": ["Kiracı", "Kiraya Veren", "Kira Bedeli"],
                    "metadata": {"source": "test"},
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["contract_type"] == "kira_sozlesmesi"
        assert "compliance_score" in body
        assert "related_articles" in body

    @pytest.mark.asyncio
    async def test_contract_types_endpoint(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/legal-analysis/contract-types")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        type_names = [t["contract_type"] for t in body]
        assert "kira_sozlesmesi" in type_names
        assert "is_sozlesmesi" in type_names

    @pytest.mark.asyncio
    async def test_contract_graph_endpoint(self, mock_repo):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/legal-analysis/contract-graph/kira_sozlesmesi"
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_contract_type_legal_analysis(self, mock_repo):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/legal-analysis/contract-legal-analysis",
                json={
                    "contract_type": "gecersiz_tip",
                    "clauses": [],
                    "metadata": {},
                },
            )
        # Geçersiz tip: 400 veya servis graceful şekilde yanıt vermeli
        assert response.status_code in (200, 400, 422)

    @pytest.mark.asyncio
    async def test_compliance_score_between_0_and_100(self, mock_repo):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/legal-analysis/contract-legal-analysis",
                json={
                    "contract_type": "is_sozlesmesi",
                    "clauses": ["İşçi", "İşveren", "Ücret"],
                    "metadata": {},
                },
            )
        assert response.status_code == 200
        score = response.json()["compliance_score"]
        assert 0.0 <= score <= 100.0


class TestAdditionalGapAnalysis:
    """Gap analysis için kapsamı genişleten edge case testleri."""

    def test_vekaletname_entities(self):
        from app.services.gap_analysis_service import run_gap_analysis
        entities = {
            "PERSON": ["Ahmet", "Mehmet"],
            "ORG": [], "MONEY": [], "DATE": ["01.01.2025"],
            "LOC": [], "CARDINAL": [], "PERCENT": [],
        }
        gap = run_gap_analysis("vekaletname", entities)
        assert gap["completeness_score"] >= 0.0
        assert "present" in gap
        assert "missing_required" in gap

    def test_kefalet_sozlesmesi_entities(self):
        from app.services.gap_analysis_service import run_gap_analysis
        entities = {
            "PERSON": ["Kefil Ad", "Alacakli Ad"],
            "ORG": [], "MONEY": ["50.000 TL"], "DATE": [],
            "LOC": [], "CARDINAL": [], "PERCENT": [],
        }
        gap = run_gap_analysis("kefalet_sozlesmesi", entities)
        assert gap["completeness_score"] >= 0.0

    def test_satis_sozlesmesi_money_mapped(self):
        from app.services.gap_analysis_service import run_gap_analysis
        entities = {
            "PERSON": ["Satici", "Alici"],
            "ORG": [], "MONEY": ["200.000 TL"], "DATE": ["15.03.2025"],
            "LOC": ["Ankara"], "CARDINAL": [], "PERCENT": [],
        }
        gap = run_gap_analysis("satis_sozlesmesi", entities)
        assert "satis_bedeli" in gap["present"]

    def test_unknown_type_returns_graceful_result(self):
        from app.services.gap_analysis_service import run_gap_analysis
        entities = {"PERSON": ["A"], "ORG": [], "MONEY": [],
                    "DATE": [], "LOC": [], "CARDINAL": [], "PERCENT": []}
        # Bilinmeyen tip → exception fırlatmamalı
        try:
            gap = run_gap_analysis("bilinmeyen_tip", entities)
            assert "completeness_score" in gap
        except (KeyError, ValueError):
            pass  # 400 fırlatmak da kabul edilebilir davranış

    def test_completeness_score_range(self):
        from app.services.gap_analysis_service import run_gap_analysis
        for contract_type in ["is_sozlesmesi", "kira_sozlesmesi", "hizmet_sozlesmesi"]:
            entities = {"PERSON": ["A"], "ORG": [], "MONEY": [],
                        "DATE": [], "LOC": [], "CARDINAL": [], "PERCENT": []}
            gap = run_gap_analysis(contract_type, entities)
            assert 0.0 <= gap["completeness_score"] <= 1.0, \
                f"{contract_type}: score={gap['completeness_score']} out of [0,1]"
