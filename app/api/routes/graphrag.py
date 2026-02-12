"""
GraphRAG API routes module.
Defines FastAPI endpoints for contract analysis and suggestion generation.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status

from app.models.response.graphrag import (
    AnalyzeInputRequest,
    ContractRequirementsDTO,
    FullAnalysisResponse,
    SuggestionsResponseDTO
)
from app.services.contract_generator import (
    ContractGenerator,
    get_contract_generator,
    ContractType
)


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


@router.get(
    "/requirements/{contract_type}",
    response_model=ContractRequirementsDTO,
    summary="Get Contract Requirements",
    description="""
    Fetch all requirements for a specific contract type from the Neo4j knowledge graph.
    
    This endpoint queries the graph for:
    - **REQUIRES** relationships (mandatory fields)
    - **RECOMMENDED** relationships (suggested fields)
    - **OPTIONAL** relationships (optional fields)
    - **DEPENDS_ON** relationships (field dependencies)
    
    The response includes the complete requirement structure needed for
    contract generation and validation.
    
    ### Supported Contract Types:
    - `hizmet_sozlesmesi` - Hizmet Sözleşmesi
    - `kira_sozlesmesi` - Kira Sözleşmesi
    - `satis_sozlesmesi` - Satış Sözleşmesi
    - `borc_sozlesmesi` - Borç Sözleşmesi
    """,
    responses={
        200: {
            "description": "Contract requirements retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "contract_type": "kira_sozlesmesi",
                        "display_name": "Kira Sözleşmesi",
                        "requires": [
                            {"node_id": 7, "name": "Kiracı", "necessity": "REQUIRES"}
                        ],
                        "recommended": [],
                        "optional": [],
                        "dependencies": [],
                        "field_mapping": {"7": "Kiracı", "8": "Kiraya Veren"}
                    }
                }
            }
        }
    }
)
async def get_requirements(contract_type: str):
    """
    Get contract requirements from Neo4j graph.
    
    Args:
        contract_type: Contract type identifier
        
    Returns:
        ContractRequirementsDTO: All requirements for the contract type
    """
    _validate_contract_type(contract_type)
    
    try:
        generator = get_contract_generator()
        requirements = generator.fetch_contract_requirements(contract_type)
        return requirements
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching requirements: {str(e)}"
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


@router.get(
    "/types",
    summary="Get Supported Contract Types",
    description="Get a list of all supported contract types with their display names.",
    responses={
        200: {
            "description": "List of supported contract types",
            "content": {
                "application/json": {
                    "example": [
                        {"id": "kira_sozlesmesi", "display_name": "Kira Sözleşmesi"},
                        {"id": "borc_sozlesmesi", "display_name": "Borç Sözleşmesi"}
                    ]
                }
            }
        }
    }
)
async def get_contract_types():
    """
    Get all supported contract types.
    
    Returns:
        List of contract types with IDs and display names
    """
    generator = get_contract_generator()
    return [
        {
            "id": ct.value,
            "display_name": generator._get_contract_display_name(ct.value),
            "field_count": len(generator.CONTRACT_FIELD_MAPPING.get(ct.value, {}))
        }
        for ct in ContractType
    ]


@router.get(
    "/field-mapping/{contract_type}",
    summary="Get Field Mapping",
    description="""
    Get the node ID to field name mapping for a specific contract type.
    
    This is useful for debugging and understanding how Neo4j node IDs
    map to human-readable field names.
    """,
    responses={
        200: {
            "description": "Field mapping retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "contract_type": "kira_sozlesmesi",
                        "mapping": {
                            "7": "Kiracı",
                            "8": "Kiraya Veren",
                            "9": "Mülk Adresi"
                        }
                    }
                }
            }
        }
    }
)
async def get_field_mapping(contract_type: str):
    """
    Get field mapping for a contract type.
    
    Args:
        contract_type: Contract type identifier
        
    Returns:
        Mapping of node IDs to field names
    """
    _validate_contract_type(contract_type)
    
    generator = get_contract_generator()
    mapping = generator.CONTRACT_FIELD_MAPPING.get(contract_type, {})
    
    return {
        "contract_type": contract_type,
        "display_name": generator._get_contract_display_name(contract_type),
        "mapping": {str(k): v for k, v in mapping.items()}
    }
