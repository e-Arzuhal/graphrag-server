"""
Contract service module.
Contains business logic for contract template operations.
"""
from typing import List, Dict, Any

from app.core.logger import get_logger
from app.db.repositories.contract_repository import ContractRepository, get_contract_repository
from app.models.response.contract import ClauseDTO, ContractTemplateResponse
from app.services.exceptions import ContractNotFoundError

logger = get_logger(__name__)


class ContractService:
    """
    Service class for contract-related business logic.
    
    This service layer acts as an intermediary between the API routes
    and the repository layer. It handles:
    - Business logic and data transformation
    - Exception handling for not-found scenarios
    - Response model construction
    
    Attributes:
        repository: The contract repository instance for database operations
    """
    
    def __init__(self, repository: ContractRepository = None):
        """
        Initialize the contract service.
        
        Args:
            repository: Optional repository instance. If not provided,
                       uses the default singleton instance.
        """
        self.repository = repository or get_contract_repository()

    def get_contract_template(self, contract_type_name: str) -> ContractTemplateResponse:
        """
        Retrieve a contract template with all its clauses.
        
        This method:
        1. Queries the repository for the contract template data
        2. Validates that the contract type exists
        3. Transforms the raw data into response models
        
        Args:
            contract_type_name: The unique identifier/name of the contract type
                               (e.g., "borc_sozlesmesi", "kira_sozlesmesi")
        
        Returns:
            ContractTemplateResponse: The contract template with all clauses
        
        Raises:
            ContractNotFoundError: If the contract type does not exist
                                  in the knowledge graph
        
        Example:
            >>> service = ContractService()
            >>> template = service.get_contract_template("borc_sozlesmesi")
            >>> print(template.display_name)
            "Borç Sözleşmesi"
            >>> print(len(template.clauses))
            5
        """
        # Query the repository for contract data
        logger.info("get_contract_template: %s", contract_type_name)
        data = self.repository.get_contract_template(contract_type_name)

        # Handle case where contract type doesn't exist
        if data is None:
            logger.warning("Contract template not found: %s", contract_type_name)
            raise ContractNotFoundError(contract_type_name)
        
        # Transform raw clause data into ClauseDTO models
        clauses = [
            ClauseDTO(
                id=clause["id"],
                template=clause["template"],
                necessity=clause["necessity"]
            )
            for clause in data.get("clauses", [])
        ]
        
        # Construct and return the response model
        return ContractTemplateResponse(
            contract_type=contract_type_name,
            display_name=data.get("display_name", ""),
            clauses=clauses
        )

    def get_all_contract_types(self) -> List[Dict[str, str]]:
        """
        Retrieve all available contract types.
        
        Returns:
            List[Dict]: A list of dictionaries containing name and display_name
                       for each available contract type
        
        Example:
            >>> service = ContractService()
            >>> types = service.get_all_contract_types()
            >>> for t in types:
            ...     print(f"{t['name']}: {t['display_name']}")
            borc_sozlesmesi: Borç Sözleşmesi
            kira_sozlesmesi: Kira Sözleşmesi
        """
        return self.repository.get_all_contract_types()

    def contract_exists(self, contract_type_name: str) -> bool:
        """
        Check if a contract type exists.
        
        Args:
            contract_type_name: The unique identifier/name of the contract type
        
        Returns:
            bool: True if the contract type exists, False otherwise
        """
        return self.repository.check_contract_exists(contract_type_name)


# Singleton instance for dependency injection
contract_service = ContractService()


def get_contract_service() -> ContractService:
    """
    Dependency injection helper for FastAPI.
    
    Returns:
        ContractService: The singleton service instance
    """
    return contract_service
