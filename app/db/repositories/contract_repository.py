"""
Contract repository module.
Contains Neo4j Cypher queries and database interactions for contract data.
"""
from typing import List, Optional, Dict, Any
from app.utils.db import neo4j_driver


class ContractRepository:
    """
    Repository class for contract-related database operations.
    
    This class encapsulates all Neo4j Cypher queries for retrieving
    contract templates and their associated clauses from the knowledge graph.
    
    The graph schema assumes:
    - Nodes: ContractType (name, display_name), Clause (id, text_template)
    - Relationships:
        - (:ContractType)-[:REQUIRES {type: "mandatory"}]->(:Clause)
        - (:ContractType)-[:INCLUDES {type: "optional"}]->(:Clause)
    """

    def get_contract_template(
        self, contract_type_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a contract template with all its clauses from the knowledge graph.
        
        This method executes a Cypher query that:
        1. Matches the ContractType node by its unique name
        2. Traverses outgoing REQUIRES and INCLUDES relationships
        3. Collects all connected Clause nodes
        4. Returns the contract display name and clause details including necessity
        
        Cypher Query Logic:
        -------------------
        MATCH (c:ContractType {name: $name})
        - Finds the ContractType node with the specified name
        
        OPTIONAL MATCH (c)-[r:REQUIRES|INCLUDES]->(cl:Clause)
        - Optionally matches all outgoing relationships to Clause nodes
        - Uses OPTIONAL to ensure we return the contract even if no clauses exist
        - Matches both REQUIRES and INCLUDES relationship types
        
        WITH c, cl, r.type as necessity
        - Carries forward the contract, clause, and relationship type (necessity)
        
        ORDER BY 
            CASE WHEN necessity = 'mandatory' THEN 0 ELSE 1 END,
            cl.id
        - Orders clauses: mandatory first, then optional, and by ID within each group
        
        RETURN c.display_name as display_name,
               collect({id: cl.id, template: cl.text_template, necessity: necessity}) as clauses
        - Returns the display name and an aggregated list of clause objects
        
        Args:
            contract_type_name: The unique identifier/name of the contract type
                               (e.g., "borc_sozlesmesi", "kira_sozlesmesi")
        
        Returns:
            Optional[Dict]: A dictionary containing:
                - display_name: Human-readable contract type name
                - clauses: List of clause dictionaries with id, template, necessity
            Returns None if the contract type is not found.
        
        Example:
            >>> repo = ContractRepository()
            >>> result = repo.get_contract_template("borc_sozlesmesi")
            >>> print(result)
            {
                "display_name": "Borç Sözleşmesi",
                "clauses": [
                    {"id": "clause_001", "template": "...", "necessity": "mandatory"},
                    {"id": "clause_002", "template": "...", "necessity": "optional"}
                ]
            }
        """
        query = """
        MATCH (c:ContractType {name: $name})
        OPTIONAL MATCH (c)-[r:REQUIRES|INCLUDES]->(cl:Clause)
        WITH c, cl, r.type as necessity
        ORDER BY 
            CASE WHEN necessity = 'mandatory' THEN 0 ELSE 1 END,
            cl.id
        RETURN 
            c.display_name as display_name,
            collect(
                CASE WHEN cl IS NOT NULL 
                THEN {id: cl.id, template: cl.text_template, necessity: necessity}
                ELSE NULL 
                END
            ) as clauses
        """
        
        with neo4j_driver.get_session() as session:
            result = session.run(query, name=contract_type_name)
            record = result.single()
            
            if record is None:
                return None
            
            data = record.data()
            
            # Filter out None values from clauses (in case of no relationships)
            data["clauses"] = [c for c in data["clauses"] if c is not None]
            
            return data

    def check_contract_exists(self, contract_type_name: str) -> bool:
        """
        Check if a contract type exists in the knowledge graph.
        
        Cypher Query Logic:
        -------------------
        MATCH (c:ContractType {name: $name})
        - Attempts to match a ContractType node with the given name
        
        RETURN count(c) > 0 as exists
        - Returns true if at least one matching node exists
        
        Args:
            contract_type_name: The unique identifier/name of the contract type
        
        Returns:
            bool: True if the contract type exists, False otherwise
        """
        query = """
        MATCH (c:ContractType {name: $name})
        RETURN count(c) > 0 as exists
        """
        
        with neo4j_driver.get_session() as session:
            result = session.run(query, name=contract_type_name)
            record = result.single()
            return record["exists"] if record else False

    def get_all_contract_types(self) -> List[Dict[str, str]]:
        """
        Retrieve all available contract types from the knowledge graph.
        
        Cypher Query Logic:
        -------------------
        MATCH (c:ContractType)
        - Matches all ContractType nodes in the graph
        
        RETURN c.name as name, c.display_name as display_name
        - Returns the technical name and display name for each contract type
        
        ORDER BY c.display_name
        - Orders results alphabetically by display name
        
        Returns:
            List[Dict]: A list of dictionaries containing name and display_name
                       for each contract type
        
        Example:
            >>> repo = ContractRepository()
            >>> types = repo.get_all_contract_types()
            >>> print(types)
            [
                {"name": "borc_sozlesmesi", "display_name": "Borç Sözleşmesi"},
                {"name": "kira_sozlesmesi", "display_name": "Kira Sözleşmesi"}
            ]
        """
        query = """
        MATCH (c:ContractType)
        RETURN c.name as name, c.display_name as display_name
        ORDER BY c.display_name
        """
        
        with neo4j_driver.get_session() as session:
            result = session.run(query)
            return [record.data() for record in result]


# Singleton instance for dependency injection
contract_repository = ContractRepository()


def get_contract_repository() -> ContractRepository:
    """
    Dependency injection helper for FastAPI.
    
    Returns:
        ContractRepository: The singleton repository instance
    """
    return contract_repository
