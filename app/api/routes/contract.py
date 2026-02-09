"""
Contract API routes module.
Defines FastAPI endpoints for contract template operations.
"""
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends, status

from app.models.response.contract import ContractTemplateResponse
from app.services.contract_service import ContractService, get_contract_service
from app.services.exceptions import ContractNotFoundError


router = APIRouter(
    prefix="/template",
    tags=["Contract Templates"],
    responses={
        404: {"description": "Contract type not found"},
        500: {"description": "Internal server error"}
    }
)


@router.get(
    "/{contract_type}",
    response_model=ContractTemplateResponse,
    summary="Get Contract Template",
    description="""
    Retrieve a contract template structure based on the contract type.
    
    This endpoint is the main entry point for the GraphRAG system. It queries
    the Neo4j knowledge graph to fetch the contract template with all its
    associated clauses (both mandatory and optional).
    
    The response includes:
    - **contract_type**: The technical identifier of the contract
    - **display_name**: Human-readable name of the contract type
    - **clauses**: List of clauses with their templates and necessity levels
    
    Clauses are ordered with mandatory clauses first, then optional ones.
    """,
    responses={
        200: {
            "description": "Contract template retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "contract_type": "borc_sozlesmesi",
                        "display_name": "Borç Sözleşmesi",
                        "clauses": [
                            {
                                "id": "clause_001",
                                "template": "İşbu sözleşme {{taraf1}} ile {{taraf2}} arasında akdedilmiştir.",
                                "necessity": "mandatory"
                            }
                        ]
                    }
                }
            }
        },
        404: {
            "description": "Contract type not found in knowledge graph",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Contract type 'unknown_type' not found in the knowledge graph"
                    }
                }
            }
        }
    }
)
async def get_contract_template(
    contract_type: str,
    service: ContractService = Depends(get_contract_service)
) -> ContractTemplateResponse:
    """
    Get the contract template structure for a given contract type.
    
    This endpoint is called by the NLP service to retrieve the template
    structure for generating legal documents.
    
    Args:
        contract_type: The unique identifier of the contract type
                      (e.g., "borc_sozlesmesi", "kira_sozlesmesi")
        service: The contract service instance (injected via dependency)
    
    Returns:
        ContractTemplateResponse: The contract template with all clauses
    
    Raises:
        HTTPException: 404 if contract type not found
        HTTPException: 500 for database or other errors
    """
    try:
        return service.get_contract_template(contract_type)
    except ContractNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the contract template: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[Dict[str, str]],
    summary="List All Contract Types",
    description="""
    Retrieve a list of all available contract types in the knowledge graph.
    
    This endpoint is useful for:
    - Populating dropdown menus in the UI
    - Validating contract type names before querying templates
    - Discovering available contract types in the system
    """,
    responses={
        200: {
            "description": "List of contract types retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {"name": "borc_sozlesmesi", "display_name": "Borç Sözleşmesi"},
                        {"name": "kira_sozlesmesi", "display_name": "Kira Sözleşmesi"}
                    ]
                }
            }
        }
    }
)
async def list_contract_types(
    service: ContractService = Depends(get_contract_service)
) -> List[Dict[str, str]]:
    """
    List all available contract types.
    
    Args:
        service: The contract service instance (injected via dependency)
    
    Returns:
        List[Dict]: A list of contract types with name and display_name
    
    Raises:
        HTTPException: 500 for database or other errors
    """
    try:
        return service.get_all_contract_types()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching contract types: {str(e)}"
        )
