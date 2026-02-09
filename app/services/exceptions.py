"""
Custom exceptions for the application.
Defines business logic exceptions that can be caught and handled by the API layer.
"""


class ContractNotFoundError(Exception):
    """
    Exception raised when a requested contract type does not exist.
    
    Attributes:
        contract_type: The contract type name that was not found
        message: Detailed error message
    """
    
    def __init__(self, contract_type: str):
        self.contract_type = contract_type
        self.message = f"Contract type '{contract_type}' not found in the knowledge graph"
        super().__init__(self.message)


class DatabaseConnectionError(Exception):
    """
    Exception raised when database connection fails.
    
    Attributes:
        message: Detailed error message
        original_error: The original exception that caused this error
    """
    
    def __init__(self, message: str = "Failed to connect to database", original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)
