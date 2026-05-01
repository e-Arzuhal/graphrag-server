"""
GraphRAG API routes module.
Defines FastAPI endpoints for contract analysis and suggestion generation.
"""
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.core.logger import get_logger
from app.models.response.graphrag import AnalyzeInputRequest
from app.data.contract_schemas import SUPPORTED_CONTRACT_TYPES
from app.data.field_tbk_mapping import FIELD_TBK_MAPPING
from app.data.question_templates import get_question
from app.services.gap_analysis_service import run_gap_analysis, needs_llm_analysis
from app.services.validation_service import run_validations
from app.services.neo4j_service import get_legal_context_for_fields
from app.services.gemini_service import analyze_with_gemini


# Statistics-server'dan beslenen kullanım yüzdeleri ileride buraya bağlanacak;
# şimdilik sabit varsayılan değerler kullanıyoruz. None dönüyorsa frontend kendi
# fallback'ine düşer.
_DEFAULT_USAGE_PERCENT = {
    "faiz_orani":     85,
    "vade":           92,
    "odeme_yontemi":  78,
    "odeme_plani":    65,
    "temerrut_faizi": 45,
    "kefalet":        30,
    "ceza_kosulu":    25,
    "yetkili_mahkeme":40,
    "depozito":       80,
    "artis_orani":    72,
    "deneme_suresi":  55,
    "ihbar_suresi":   60,
    "sure":           70,
    "bitis_tarihi":   58,
    "teslim_yeri":    50,
    "yetki_kapsami":  68,
    "taraf_2":        20,
}

logger = get_logger(__name__)

_api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


async def verify_internal_key(key: str = Security(_api_key_header)) -> None:
    settings = get_settings()
    if not key or key != settings.internal_api_key:
        logger.warning("Rejected request: invalid or missing X-Internal-API-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key.",
        )


router = APIRouter(
    prefix="/analyze",
    tags=["GraphRAG Analysis"],
    responses={
        400: {"description": "Invalid contract type"},
        500: {"description": "Internal server error"},
    }
)


def _validate_contract_type(contract_type: str) -> None:
    if contract_type not in SUPPORTED_CONTRACT_TYPES:
        logger.warning("Rejected unsupported contract type: %s", contract_type)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid contract type: {contract_type}",
                "valid_types": SUPPORTED_CONTRACT_TYPES,
            }
        )


@router.post(
    "/input",
    summary="Analyze User Input",
    description="""
    Analyzes spaCy-extracted entities against the contract schema.

    Pipeline:
    1. **Gap Analysis** — maps entities to semantic fields, calculates completeness score
    2. **Validation** — rule-based TBK checks (e.g. deneme_suresi max 2 ay)
    3. **Decision Gate** — skips LLM if no missing required fields and no errors
    4. **Neo4j** — fetches graph context for problematic fields (conditional)
    5. **Gemini** — legal risk analysis with TBK references (conditional)
    6. **Response** — structured result with chatbot questions

    ### Entity Types (spaCy format):
    - `PERSON`: Person names
    - `ORG`: Organizations
    - `MONEY`: Monetary values
    - `DATE`: Dates
    - `LOC`: Locations
    - `CARDINAL`: Numbers/durations
    - `PERCENT`: Percentages
    """,
)
async def analyze_input(
    request: AnalyzeInputRequest,
    _: None = Depends(verify_internal_key),
):
    _validate_contract_type(request.contract_type)

    contract_type      = request.contract_type
    extracted_entities = request.extracted_entities

    logger.info(
        "POST /analyze/input: contract_type=%s entity_types=%s",
        contract_type, list(extracted_entities.keys()),
    )

    # 1. Gap Analysis
    gap = run_gap_analysis(contract_type, extracted_entities)

    # 2. Validation
    validation_errors = run_validations(contract_type, extracted_entities)

    # 3. Decision Gate
    use_llm          = needs_llm_analysis(gap["missing_required"], validation_errors)
    legal_analysis   = None
    compliance_score = gap["completeness_score"]
    logger.debug("Decision gate: use_llm=%s", use_llm)

    if use_llm:
        # 4. Neo4j — fetch graph context for missing/invalid fields
        problematic = gap["missing_required"] + [e["field"] for e in validation_errors]
        neo4j_ctx   = await get_legal_context_for_fields(
            fields=list(set(problematic)),
            field_mapping=FIELD_TBK_MAPPING,
        )

        # 5. Gemini — legal risk analysis
        gemini_result  = await analyze_with_gemini(
            contract_type=contract_type,
            present_fields=gap["present"],
            missing_required=gap["missing_required"],
            missing_optional=gap["missing_optional"],
            validation_errors=validation_errors,
            neo4j_context=neo4j_ctx,
        )
        legal_analysis   = gemini_result
        compliance_score = round(
            max(0.0, gap["completeness_score"] - gemini_result.get("compliance_penalty", 0.0)), 2
        )

    # 6. Chatbot questions — required first, then optional
    questions    = []
    suggestions  = []
    priority     = 1
    for field in gap["missing_required"]:
        q_text = get_question(field)
        questions.append({
            "priority": priority,
            "field":    field,
            "question": q_text,
            "required": True,
        })
        suggestions.append({
            "field_name":    field,
            "message":       q_text,
            "necessity":     "required",
            "usage_percent": _DEFAULT_USAGE_PERCENT.get(field),
        })
        priority += 1
    for field in gap["missing_optional"]:
        q_text = get_question(field)
        questions.append({
            "priority": priority,
            "field":    field,
            "question": q_text,
            "required": False,
        })
        suggestions.append({
            "field_name":    field,
            "message":       q_text,
            "necessity":     "recommended",
            "usage_percent": _DEFAULT_USAGE_PERCENT.get(field),
        })
        priority += 1

    return {
        "analysis": {
            "contract_type":      contract_type,
            "completeness_score": round(gap["completeness_score"] * 100, 1),
            "compliance_score":   round(compliance_score * 100, 1),
            "needs_llm_analysis": use_llm,
            "matched_fields":     gap["present"],
            "missing_required":   gap["missing_required"],
            "missing_optional":   gap["missing_optional"],
            "validation_errors":  validation_errors,
        },
        "suggestions": {
            "status":            "complete" if not gap["missing_required"] else "incomplete",
            "next_action":       questions[0]["question"] if questions else None,
            "chatbot_questions": questions,
            # Frontend (`realResult.graphrag_result?.suggestions?.suggestions`) bu listeyi okur.
            # `chatbot_questions` geriye uyumluluk için korundu.
            "suggestions":       suggestions,
        },
        "legal_analysis": legal_analysis,
        "graph_data":     {},
    }
