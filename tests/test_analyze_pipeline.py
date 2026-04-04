"""
Tests for the analyze/input pipeline.

Covers:
  - gap_analysis_service  (unit)
  - validation_service    (unit)
  - analyze_input endpoint (integration — Neo4j and Gemini are mocked)
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.gap_analysis_service import run_gap_analysis, needs_llm_analysis
from app.services.validation_service import run_validations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_IS_SOZLESMESI_ENTITIES = {
    "PERSON":   ["Ahmet Yılmaz"],
    "ORG":      ["ABC A.Ş."],
    "MONEY":    ["25.000 TL"],
    "DATE":     ["01.03.2025"],
    "LOC":      ["İstanbul"],
    "CARDINAL": ["2 ay"],
    "PERCENT":  [],
}

PARTIAL_IS_SOZLESMESI_ENTITIES = {
    "PERSON":   ["Ahmet Yılmaz"],
    "ORG":      ["ABC A.Ş."],
    "MONEY":    ["25.000 TL"],
    "DATE":     ["01.03.2025"],
    "LOC":      [],
    "CARDINAL": ["2 ay"],
    "PERCENT":  [],
}

MOCK_GEMINI_RESULT = {
    "tbk_articles": [393, 419],
    "risks": [
        {
            "field": "is_tanimi",
            "risk_level": "HIGH",
            "tbk_article": 393,
            "explanation": "İş tanımı eksik.",
            "suggestion": "Pozisyon ve görev tanımını ekleyin.",
        }
    ],
    "general_assessment": "Sözleşmede eksik alanlar tespit edildi.",
    "compliance_penalty": 0.15,
}


# ---------------------------------------------------------------------------
# Unit — gap_analysis_service
# ---------------------------------------------------------------------------

class TestGapAnalysisService:

    def test_is_sozlesmesi_partial_entities(self):
        gap = run_gap_analysis("is_sozlesmesi", PARTIAL_IS_SOZLESMESI_ENTITIES)

        assert "taraf_isci"     in gap["present"]
        assert "taraf_isveren"  in gap["present"]
        assert "ucret"          in gap["present"]
        assert "baslangic_tarihi" in gap["present"]
        assert "deneme_suresi"  in gap["present"]

        assert "is_tanimi"   in gap["missing_required"]
        assert "calisma_yeri" in gap["missing_required"]

        assert gap["completeness_score"] == pytest.approx(0.67, abs=0.01)

    def test_is_sozlesmesi_full_entities(self):
        gap = run_gap_analysis("is_sozlesmesi", FULL_IS_SOZLESMESI_ENTITIES)

        assert "calisma_yeri" in gap["present"]
        assert "is_tanimi"    not in gap["present"]   # no text entity maps to is_tanimi
        assert gap["completeness_score"] < 1.0        # is_tanimi still missing

    def test_kira_sozlesmesi_happy_path(self):
        entities = {
            "PERSON":   ["Ahmet", "Mehmet"],
            "ORG":      [],
            "MONEY":    ["5000 TL"],
            "DATE":     ["01.03.2025"],
            "LOC":      ["Kadıköy"],
            "CARDINAL": [],
            "PERCENT":  ["TÜFE+5"],
        }
        gap = run_gap_analysis("kira_sozlesmesi", entities)

        assert "taraf_kiraci"      in gap["present"]
        assert "taraf_kiraya_veren" in gap["present"]
        assert "kira_bedeli"       in gap["present"]
        assert "kiralanan_adres"   in gap["present"]
        assert "artis_orani"       in gap["present"]

    def test_completeness_score_zero_when_no_entities(self):
        empty = {"PERSON": [], "ORG": [], "MONEY": [], "DATE": [],
                 "LOC": [], "CARDINAL": [], "PERCENT": []}
        gap = run_gap_analysis("is_sozlesmesi", empty)
        assert gap["completeness_score"] == 0.0
        assert len(gap["missing_required"]) > 0

    def test_completeness_score_full(self):
        """Unknown contract type — only 2 required fields, both easily met."""
        entities = {
            "PERSON": ["A", "B"], "ORG": [], "MONEY": [],
            "DATE": ["01.01.2025"], "LOC": [], "CARDINAL": [], "PERCENT": [],
        }
        gap = run_gap_analysis("taahhutname", entities)
        assert gap["completeness_score"] == 1.0
        assert gap["missing_required"] == []

    def test_needs_llm_true_when_missing_required(self):
        assert needs_llm_analysis(["is_tanimi"], []) is True

    def test_needs_llm_true_when_validation_errors(self):
        assert needs_llm_analysis([], [{"field": "deneme_suresi"}]) is True

    def test_needs_llm_false_when_nothing_missing(self):
        assert needs_llm_analysis([], []) is False


# ---------------------------------------------------------------------------
# Unit — validation_service
# ---------------------------------------------------------------------------

class TestValidationService:

    def test_deneme_suresi_violation(self):
        errors = run_validations("is_sozlesmesi", {"CARDINAL": ["3 ay"]})
        assert len(errors) == 1
        assert errors[0]["field"] == "deneme_suresi"
        assert "TBK m.393" in errors[0]["tbk_limit"]

    def test_deneme_suresi_at_limit_no_error(self):
        errors = run_validations("is_sozlesmesi", {"CARDINAL": ["2 ay"]})
        assert errors == []

    def test_ihbar_suresi_violation(self):
        errors = run_validations("is_sozlesmesi", {"CARDINAL": ["1 hafta"]})
        assert len(errors) == 1
        assert errors[0]["field"] == "ihbar_suresi"
        assert "TBK m.432" in errors[0]["tbk_limit"]

    def test_ihbar_suresi_at_limit_no_error(self):
        errors = run_validations("is_sozlesmesi", {"CARDINAL": ["2 hafta"]})
        assert errors == []

    def test_multiple_violations(self):
        errors = run_validations("is_sozlesmesi", {"CARDINAL": ["3 ay", "1 hafta"]})
        fields = [e["field"] for e in errors]
        assert "deneme_suresi" in fields
        assert "ihbar_suresi"  in fields

    def test_no_rules_for_kira(self):
        errors = run_validations("kira_sozlesmesi", {"CARDINAL": ["3 ay"]})
        assert errors == []

    def test_empty_cardinals(self):
        errors = run_validations("is_sozlesmesi", {"CARDINAL": []})
        assert errors == []


# ---------------------------------------------------------------------------
# Integration — POST /api/v1/analyze/input
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_neo4j_empty():
    """Neo4j returns no graph data (simulates empty or offline DB)."""
    with patch(
        "app.api.routes.graphrag.get_legal_context_for_fields",
        new_callable=AsyncMock,
        return_value={"is_tanimi": [], "calisma_yeri": []},
    ):
        yield


@pytest.fixture
def mock_gemini_success():
    """Gemini returns a valid analysis result."""
    with patch(
        "app.api.routes.graphrag.analyze_with_gemini",
        new_callable=AsyncMock,
        return_value=MOCK_GEMINI_RESULT,
    ):
        yield


@pytest.fixture
def mock_gemini_fallback():
    """Gemini returns the fallback structure (simulates quota/network error)."""
    fallback = {
        "tbk_articles": [],
        "risks": [{"field": "is_tanimi", "risk_level": "HIGH",
                   "tbk_article": None, "explanation": "Eksik.",
                   "suggestion": "Ekleyin."}],
        "general_assessment": "Otomatik analiz tamamlanamadı.",
        "compliance_penalty": 0.3,
    }
    with patch(
        "app.api.routes.graphrag.analyze_with_gemini",
        new_callable=AsyncMock,
        return_value=fallback,
    ):
        yield


class TestAnalyzeInputEndpoint:

    @pytest.mark.asyncio
    async def test_partial_contract_returns_incomplete(
        self, mock_neo4j_empty, mock_gemini_success
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/analyze/input",
                json={
                    "contract_type": "is_sozlesmesi",
                    "extracted_entities": PARTIAL_IS_SOZLESMESI_ENTITIES,
                },
            )

        assert response.status_code == 200
        body = response.json()

        assert body["analysis"]["contract_type"] == "is_sozlesmesi"
        assert body["analysis"]["completeness_score"] == pytest.approx(67.0, abs=1.0)
        assert body["analysis"]["needs_llm_analysis"] is True
        assert "is_tanimi"    in body["analysis"]["missing_required"]
        assert "calisma_yeri" in body["analysis"]["missing_required"]

        assert body["suggestions"]["status"] == "incomplete"
        assert body["suggestions"]["next_action"] is not None
        assert len(body["suggestions"]["chatbot_questions"]) >= 2

        assert body["legal_analysis"] is not None
        assert 393 in body["legal_analysis"]["tbk_articles"]

    @pytest.mark.asyncio
    async def test_compliance_score_reduced_by_penalty(
        self, mock_neo4j_empty, mock_gemini_success
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/analyze/input",
                json={
                    "contract_type": "is_sozlesmesi",
                    "extracted_entities": PARTIAL_IS_SOZLESMESI_ENTITIES,
                },
            )
        body = response.json()
        # completeness=0.67, penalty=0.15 → compliance = (0.67-0.15)*100 = 52.0
        assert body["analysis"]["compliance_score"] < body["analysis"]["completeness_score"]

    @pytest.mark.asyncio
    async def test_chatbot_questions_order(
        self, mock_neo4j_empty, mock_gemini_success
    ):
        """Required questions must come before optional ones."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/analyze/input",
                json={
                    "contract_type": "is_sozlesmesi",
                    "extracted_entities": PARTIAL_IS_SOZLESMESI_ENTITIES,
                },
            )
        questions = response.json()["suggestions"]["chatbot_questions"]
        required_priorities   = [q["priority"] for q in questions if q["required"]]
        optional_priorities   = [q["priority"] for q in questions if not q["required"]]
        assert max(required_priorities) < min(optional_priorities)

    @pytest.mark.asyncio
    async def test_validation_error_included_in_response(
        self, mock_neo4j_empty, mock_gemini_success
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/analyze/input",
                json={
                    "contract_type": "is_sozlesmesi",
                    "extracted_entities": {
                        **PARTIAL_IS_SOZLESMESI_ENTITIES,
                        "CARDINAL": ["3 ay"],   # violates TBK m.393
                    },
                },
            )
        body = response.json()
        assert len(body["analysis"]["validation_errors"]) == 1
        assert body["analysis"]["validation_errors"][0]["field"] == "deneme_suresi"

    @pytest.mark.asyncio
    async def test_complete_contract_skips_llm(self):
        """When all required fields are present and no validation errors, LLM is not called."""
        full_taahhutname = {
            "PERSON":   ["A", "B"],
            "ORG":      [],
            "MONEY":    [],
            "DATE":     ["01.01.2025"],
            "LOC":      [],
            "CARDINAL": [],
            "PERCENT":  [],
        }
        with patch(
            "app.api.routes.graphrag.analyze_with_gemini",
            new_callable=AsyncMock,
        ) as mock_gemini:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/analyze/input",
                    json={
                        "contract_type": "taahhutname",
                        "extracted_entities": full_taahhutname,
                    },
                )
            mock_gemini.assert_not_called()

        body = response.json()
        assert body["analysis"]["needs_llm_analysis"] is False
        assert body["legal_analysis"] is None
        assert body["suggestions"]["status"] == "complete"

    @pytest.mark.asyncio
    async def test_gemini_fallback_still_returns_200(
        self, mock_neo4j_empty, mock_gemini_fallback
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/analyze/input",
                json={
                    "contract_type": "is_sozlesmesi",
                    "extracted_entities": PARTIAL_IS_SOZLESMESI_ENTITIES,
                },
            )
        assert response.status_code == 200
        assert response.json()["legal_analysis"] is not None

    @pytest.mark.asyncio
    async def test_invalid_contract_type_returns_400(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/analyze/input",
                json={
                    "contract_type": "gecersiz_tip",
                    "extracted_entities": {},
                },
            )
        assert response.status_code == 400
        assert "valid_types" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_all_supported_contract_types_accepted(
        self, mock_neo4j_empty, mock_gemini_fallback
    ):
        """Every type in SUPPORTED_CONTRACT_TYPES must return 200."""
        from app.data.contract_schemas import SUPPORTED_CONTRACT_TYPES
        empty_entities = {
            "PERSON": [], "ORG": [], "MONEY": [],
            "DATE": [], "LOC": [], "CARDINAL": [], "PERCENT": [],
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for ct in SUPPORTED_CONTRACT_TYPES:
                response = await client.post(
                    "/api/v1/analyze/input",
                    json={"contract_type": ct, "extracted_entities": empty_entities},
                )
                assert response.status_code == 200, f"Failed for contract type: {ct}"


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoints:

    @pytest.mark.asyncio
    async def test_root_returns_healthy(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_endpoint_structure(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert "status"     in body
        assert "components" in body
        assert "neo4j"      in body["components"]
