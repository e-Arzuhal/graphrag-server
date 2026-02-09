"""
Contract response models.
Defines Pydantic models for contract template API responses.
"""
from typing import List, Literal
from pydantic import BaseModel, Field


class ClauseDTO(BaseModel):
    """
    Data Transfer Object for a contract clause.
    
    Represents a single clause in a contract template with its
    text template and necessity level (mandatory or optional).
    
    Attributes:
        id: Unique identifier for the clause
        template: The text template of the clause with placeholders
        necessity: Whether the clause is mandatory or optional
    
    Example:
        {
            "id": "clause_001",
            "template": "Taraflar arasında {{tarih}} tarihinde...",
            "necessity": "mandatory"
        }
    """
    id: str = Field(
        ...,
        description="Unique identifier for the clause",
        examples=["clause_001"]
    )
    template: str = Field(
        ...,
        description="The text template of the clause with placeholders",
        examples=["Taraflar arasında {{tarih}} tarihinde..."]
    )
    necessity: Literal["mandatory", "optional"] = Field(
        ...,
        description="Whether the clause is mandatory or optional in the contract",
        examples=["mandatory"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "clause_001",
                "template": "İşbu sözleşme {{taraf1}} ile {{taraf2}} arasında akdedilmiştir.",
                "necessity": "mandatory"
            }
        }


class ContractTemplateResponse(BaseModel):
    """
    Response model for contract template retrieval.
    
    Contains the contract type information and all associated clauses
    retrieved from the knowledge graph.
    
    Attributes:
        contract_type: The technical name/identifier of the contract type
        display_name: Human-readable name of the contract type
        clauses: List of clauses associated with this contract type
    
    Example:
        {
            "contract_type": "borc_sozlesmesi",
            "display_name": "Borç Sözleşmesi",
            "clauses": [
                {
                    "id": "clause_001",
                    "template": "...",
                    "necessity": "mandatory"
                }
            ]
        }
    """
    contract_type: str = Field(
        ...,
        description="The technical name/identifier of the contract type",
        examples=["borc_sozlesmesi"]
    )
    display_name: str = Field(
        ...,
        description="Human-readable name of the contract type",
        examples=["Borç Sözleşmesi"]
    )
    clauses: List[ClauseDTO] = Field(
        default_factory=list,
        description="List of clauses associated with this contract type"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "contract_type": "borc_sozlesmesi",
                "display_name": "Borç Sözleşmesi",
                "clauses": [
                    {
                        "id": "clause_001",
                        "template": "İşbu sözleşme {{taraf1}} ile {{taraf2}} arasında akdedilmiştir.",
                        "necessity": "mandatory"
                    },
                    {
                        "id": "clause_002",
                        "template": "Borç miktarı {{miktar}} TL olarak belirlenmiştir.",
                        "necessity": "mandatory"
                    },
                    {
                        "id": "clause_003",
                        "template": "Teminat olarak {{teminat}} sunulabilir.",
                        "necessity": "optional"
                    }
                ]
            }
        }
