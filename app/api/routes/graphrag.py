"""
GraphRAG API routes module.
Defines FastAPI endpoints for contract analysis and suggestion generation.
"""
from fastapi import APIRouter, HTTPException, status

from app.models.response.graphrag import (
    AnalyzeInputRequest,
)
from app.services.contract_generator import get_contract_generator
from app.services.contract_types import ContractType


router = APIRouter(
    prefix="/analyze",
    tags=["GraphRAG Analysis"],
    responses={
        400: {"description": "Invalid contract type"},
        404: {"description": "Contract type not found"},
        500: {"description": "Internal server error"}
    }
)


# Valid contract types
VALID_CONTRACT_TYPES = {ct.value for ct in ContractType}


def _validate_contract_type(contract_type: str) -> None:
    """Validate that the contract type is supported."""
    if contract_type not in VALID_CONTRACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": f"Invalid contract type: {contract_type}",
                "valid_types": list(VALID_CONTRACT_TYPES)
            }
        )



@router.post(
    "/input",
    summary="Analyze User Input",
    description="""
    Analyze user input entities against contract requirements.
    
    This endpoint is the main entry point for the GraphRAG analysis system.
    It takes extracted entities from spaCy NLP and compares them against
    the knowledge graph to:
    
    1. **Match entities** to required/recommended/optional fields
    2. **Identify missing** mandatory fields
    3. **Calculate completeness** score
    4. **Generate suggestions** for the user
    5. **Create LLM prompt** for further processing
    
    ### Entity Types from spaCy:
    - `PERSON`: Person names (maps to parties like Kiracı, Alacaklı)
    - `ORG`: Organizations
    - `MONEY`: Monetary values (maps to Ücret, Kira Bedeli)
    - `DATE`: Dates (maps to Teslim Tarihi, Tarih)
    - `LOC`: Locations (maps to Mülk Adresi)
    - `CARDINAL`: Numbers
    - `PERCENT`: Percentages (maps to Artış Oranı)
    
    ### Response Structure:
    - `analysis`: Detailed comparison results
    - `suggestions`: Proactive questions and reminders
    - `graph_data`: Raw requirements from Neo4j
    """,
    responses={
        200: {
            "description": "Analysis completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "analysis": {
                            "contract_type": "kira_sozlesmesi",
                            "completeness_score": 40.0,
                            "matched_fields": [],
                            "missing_required": []
                        },
                        "suggestions": {
                            "status": "incomplete",
                            "next_action": "Kullanıcıya şu soruyu sor: ...",
                            "llm_prompt": "## Sözleşme Analiz Raporu..."
                        },
                        "graph_data": {}
                    }
                }
            }
        }
    }
)
async def analyze_input(request: AnalyzeInputRequest):
    """
    Analyze extracted entities against contract requirements.
    
    Args:
        request: Contains contract_type and extracted_entities
        
    Returns:
        Full analysis result with suggestions
    """
    _validate_contract_type(request.contract_type)
    
    try:
        generator = get_contract_generator()
        result = generator.analyze_user_input(
            contract_type=request.contract_type,
            extracted_entities=request.extracted_entities
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing input: {str(e)}"
        )