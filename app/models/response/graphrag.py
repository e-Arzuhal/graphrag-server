"""
GraphRAG response models.
Defines Pydantic models for contract analysis and suggestion API responses.
"""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class ContractFieldDTO(BaseModel):
    """
    Data Transfer Object for a contract field requirement.
    
    Represents a single field/requirement in a contract with its
    necessity level and dependencies.
    
    Attributes:
        node_id: Neo4j node ID for this field
        name: Human-readable field name
        necessity: REQUIRES, RECOMMENDED, or OPTIONAL
        description: Optional description of the field
        depends_on: List of node IDs this field depends on
    """
    node_id: int = Field(
        ...,
        description="Neo4j node ID for this field"
    )
    name: str = Field(
        ...,
        description="Human-readable field name",
        examples=["Kiracı", "Kira Bedeli"]
    )
    necessity: Literal["REQUIRES", "RECOMMENDED", "OPTIONAL"] = Field(
        ...,
        description="Necessity level of this field"
    )
    description: Optional[str] = Field(
        None,
        description="Optional description of the field"
    )
    depends_on: List[int] = Field(
        default_factory=list,
        description="List of node IDs this field depends on"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": 7,
                "name": "Kiracı",
                "necessity": "REQUIRES",
                "description": "Kiracının tam adı ve kimlik bilgileri",
                "depends_on": []
            }
        }


class SuggestionDTO(BaseModel):
    """
    Data Transfer Object for a proactive suggestion.
    
    Represents a suggestion to show the user about missing
    or recommended information.
    """
    type: Literal["question", "reminder", "info"] = Field(
        ...,
        description="Type of suggestion"
    )
    field_name: str = Field(
        ...,
        description="Name of the related field"
    )
    message: str = Field(
        ...,
        description="The suggestion message to show the user"
    )
    priority: int = Field(
        ...,
        description="Priority level (1=highest, 3=lowest)",
        ge=1,
        le=3
    )
    necessity: Literal["required", "recommended", "optional"] = Field(
        ...,
        description="Necessity level of the related field"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "type": "question",
                "field_name": "Kiracı",
                "message": "Kiracının adı ve soyadı nedir?",
                "priority": 1,
                "necessity": "required"
            }
        }


class AnalysisResultDTO(BaseModel):
    """
    Data Transfer Object for the analysis result.
    
    Contains the results of comparing extracted entities
    with graph requirements.
    """
    contract_type: str = Field(
        ...,
        description="Contract type identifier"
    )
    extracted_entities: Dict[str, Any] = Field(
        ...,
        description="Entities extracted from user input"
    )
    matched_fields: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Fields successfully matched from input"
    )
    missing_required: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Required fields that are missing"
    )
    missing_recommended: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Recommended fields that are missing"
    )
    missing_optional: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Optional fields that are missing"
    )
    completeness_score: float = Field(
        ...,
        description="Percentage of required fields matched (0-100)",
        ge=0,
        le=100
    )

    class Config:
        json_schema_extra = {
            "example": {
                "contract_type": "kira_sozlesmesi",
                "extracted_entities": {
                    "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
                    "MONEY": ["5000 TL"]
                },
                "matched_fields": [],
                "missing_required": [],
                "missing_recommended": [],
                "missing_optional": [],
                "completeness_score": 60.0
            }
        }


class SuggestionsResponseDTO(BaseModel):
    """
    Data Transfer Object for the suggestions response.
    
    Contains all suggestions and LLM-ready prompt.
    """
    contract_type: str = Field(
        ...,
        description="Contract type identifier"
    )
    display_name: str = Field(
        ...,
        description="Human-readable contract type name"
    )
    completeness_score: float = Field(
        ...,
        description="Percentage of required fields completed"
    )
    status: Literal["incomplete", "needs_review", "complete"] = Field(
        ...,
        description="Overall status of the contract"
    )
    matched_fields_count: int = Field(
        ...,
        description="Number of fields successfully matched"
    )
    missing_required_count: int = Field(
        ...,
        description="Number of required fields still missing"
    )
    missing_recommended_count: int = Field(
        ...,
        description="Number of recommended fields still missing"
    )
    suggestions: List[SuggestionDTO] = Field(
        default_factory=list,
        description="List of proactive suggestions"
    )
    next_action: str = Field(
        ...,
        description="Suggested next action for the system"
    )
    llm_prompt: str = Field(
        ...,
        description="Ready-to-use prompt for LLM processing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "contract_type": "kira_sozlesmesi",
                "display_name": "Kira Sözleşmesi",
                "completeness_score": 40.0,
                "status": "incomplete",
                "matched_fields_count": 2,
                "missing_required_count": 3,
                "missing_recommended_count": 2,
                "suggestions": [],
                "next_action": "Kullanıcıya şu soruyu sor: Mülk adresi nedir?",
                "llm_prompt": "## Sözleşme Analiz Raporu..."
            }
        }


class ContractRequirementsDTO(BaseModel):
    """
    Data Transfer Object for contract requirements.
    
    Contains all requirements fetched from Neo4j graph.
    """
    contract_type: str = Field(
        ...,
        description="Contract type identifier"
    )
    display_name: str = Field(
        ...,
        description="Human-readable contract type name"
    )
    requires: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Mandatory fields"
    )
    recommended: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Recommended fields"
    )
    optional: List[ContractFieldDTO] = Field(
        default_factory=list,
        description="Optional fields"
    )
    dependencies: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Field dependencies"
    )
    field_mapping: Dict[int, str] = Field(
        default_factory=dict,
        description="Mapping of node IDs to field names"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "contract_type": "kira_sozlesmesi",
                "display_name": "Kira Sözleşmesi",
                "requires": [],
                "recommended": [],
                "optional": [],
                "dependencies": [],
                "field_mapping": {7: "Kiracı", 8: "Kiraya Veren"}
            }
        }


class AnalyzeInputRequest(BaseModel):
    """
    Request model for analyzing user input.
    """
    contract_type: str = Field(
        ...,
        description="Contract type to analyze",
        examples=["kira_sozlesmesi", "borc_sozlesmesi", "satis_sozlesmesi", "hizmet_sozlesmesi"]
    )
    extracted_entities: Dict[str, List[str]] = Field(
        ...,
        description="Entities extracted from user input by NLP",
        examples=[{
            "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
            "MONEY": ["5000 TL"],
            "DATE": ["01.03.2024"],
            "LOC": ["Istanbul, Kadıköy"]
        }]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "contract_type": "kira_sozlesmesi",
                "extracted_entities": {
                    "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
                    "MONEY": ["5000 TL"],
                    "DATE": ["01.03.2024"],
                    "LOC": ["Istanbul, Kadıköy"]
                }
            }
        }


class FullAnalysisResponse(BaseModel):
    """
    Complete analysis response including all data.
    """
    analysis: AnalysisResultDTO = Field(
        ...,
        description="Analysis result with matched/missing fields"
    )
    suggestions: SuggestionsResponseDTO = Field(
        ...,
        description="Proactive suggestions for the user"
    )
    graph_data: ContractRequirementsDTO = Field(
        ...,
        description="Raw graph data used for analysis"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "analysis": {},
                "suggestions": {},
                "graph_data": {}
            }
        }
