"""
Legal Analysis Router

Exposes two endpoints consumed exclusively by main-server (GraphRagService.java):

  POST /api/v1/legal-analysis/contract-legal-analysis
  GET  /api/v1/legal-analysis/contract-graph/{contract_type}

Auth: All requests from main-server must carry the X-Internal-API-Key header.
The dependency `verify_internal_key` enforces this.

Add this router to main.py:
    from app.api.routes.legal_analysis import router as legal_analysis_router
    app.include_router(legal_analysis_router, prefix="/api/v1")
"""
import os
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from app.services.legal_analysis_service import (
    LegalAnalysisService,
    get_legal_analysis_service,
)
from app.services.contract_types import ContractType


# ---------------------------------------------------------------------------
# Internal key auth — mirrors main-server's INTERNAL_API_KEY mechanism
# ---------------------------------------------------------------------------

def verify_internal_key(x_internal_api_key: Optional[str] = Header(default=None)):
    """
    Reject requests that don't carry the shared internal API key.
    Set INTERNAL_API_KEY env var on both main-server and graphrag-server.
    In development, the check is skipped when the env var is not set.
    """
    expected = os.getenv("INTERNAL_API_KEY")
    if expected and x_internal_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-API-Key header.",
        )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ContractLegalAnalysisRequest(BaseModel):
    """
    Request body for POST /contract-legal-analysis.
    Sent by main-server AnalysisService after NLP processing.
    """
    contract_type: str = Field(
        ...,
        description="Turkish contract type identifier, e.g. 'kira_sozlesmesi'",
        examples=["kira_sozlesmesi"],
    )
    clauses: List[str] = Field(
        default_factory=list,
        description=(
            "List of field names or clause texts present in the contract. "
            "Plain field names like 'Kiracı', 'Kira Bedeli' work best."
        ),
        examples=[["Kiracı", "Kira Bedeli", "Mülk Adresi"]],
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra metadata (reserved for future use).",
    )


class LegalArticleOut(BaseModel):
    article_id:     str
    law_name:       str
    article_number: str
    summary:        str
    legal_topics:   List[str]
    obligations:    List[str]
    penalties:      List[str]
    references:     List[str]
    relevance_score: float


class ContractLegalAnalysisResponse(BaseModel):
    contract_type:               str
    display_name:                str
    related_articles:            List[LegalArticleOut]
    compliance_score:            float = Field(..., description="0-100 score")
    potential_conflicts:         List[str]
    suggested_missing_articles:  List[str]
    missing_required_fields:     List[str]


class ClauseOut(BaseModel):
    name:        str
    description: str
    depends_on:  List[str] = Field(default_factory=list)


class CrossRefOut(BaseModel):
    from_field:   str = Field(alias="from")
    to_field:     str = Field(alias="to")
    relationship: str

    class Config:
        populate_by_name = True


class ContractGraphResponse(BaseModel):
    contract_type:    str
    display_name:     str
    mandatory_clauses: List[ClauseOut]
    optional_clauses:  List[ClauseOut]
    cross_references:  List[Dict[str, str]]
    related_risks:     List[str]
    law_articles:      List[LegalArticleOut]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/legal-analysis",
    tags=["Legal Analysis"],
    dependencies=[Depends(verify_internal_key)],
)


@router.post(
    "/contract-legal-analysis",
    response_model=ContractLegalAnalysisResponse,
    summary="Analyze a contract against the knowledge graph",
    description="""
Given a contract type and the fields/clauses it contains, returns:
- Relevant Turkish law articles (from Neo4j or fallback stubs)
- A compliance score based on required field coverage
- Detected rule violations / potential conflicts
- Missing required fields

Called by **main-server only** via `GraphRagService.java`.
""",
)
async def contract_legal_analysis(
    request: ContractLegalAnalysisRequest,
    service: LegalAnalysisService = Depends(get_legal_analysis_service),
):
    try:
        result = service.analyze_contract(
            contract_type=request.contract_type,
            clauses=request.clauses,
            metadata=request.metadata,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


@router.get(
    "/contract-graph/{contract_type}",
    response_model=ContractGraphResponse,
    summary="Get full graph structure for a contract type",
    description="""
Returns the complete structured graph for a contract type including:
- Mandatory and optional clauses
- Dependencies between clauses
- Related legal risks
- Relevant law articles

Used by UI (clause selection), chatbot (via main-server), and analytics layer.
""",
)
async def get_contract_graph(
    contract_type: str,
    service: LegalAnalysisService = Depends(get_legal_analysis_service),
):
    try:
        result = service.get_contract_graph(contract_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph retrieval failed: {str(e)}",
        )


@router.get(
    "/contract-types",
    summary="List all supported contract types",
    description="Returns all valid contract type identifiers and their display names.",
)
async def list_contract_types():
    """Utility endpoint — lets main-server validate contract types before calling analyze."""
    from app.services.contract_types import DISPLAY_NAMES
    return [
        {"name": ct.value, "display_name": DISPLAY_NAMES[ct.value]}
        for ct in ContractType
    ]