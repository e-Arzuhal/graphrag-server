"""
Contract repository module.
Contains Neo4j Cypher queries and database interactions for contract data.
"""
from typing import Any, Dict, List, Optional

from app.utils.db import Neo4jDriver


class ContractRepository:
    """Repository for contract-related Neo4j operations."""
    
    # Display name mapping for contract types
    DISPLAY_NAMES = {
        "hizmet_sozlesmesi": "Hizmet Sözleşmesi",
        "kira_sozlesmesi": "Kira Sözleşmesi", 
        "satis_sozlesmesi": "Satış Sözleşmesi",
        "borc_sozlesmesi": "Borç Sözleşmesi",
        "HizmetSozlesmesi": "Hizmet Sözleşmesi",
        "KiraSozlesmesi": "Kira Sözleşmesi",
        "SatisSozlesmesi": "Satış Sözleşmesi",
        "BorcSozlesmesi": "Borç Sözleşmesi",
    }
    
    def __init__(self):
        self.driver = Neo4jDriver()
    
    def _get_display_name(self, contract_type: str, db_display_name: Optional[str] = None) -> str:
        """Get display name with fallback logic."""
        if db_display_name:
            return db_display_name
        return self.DISPLAY_NAMES.get(contract_type, contract_type.replace("_", " ").title())
    
    def get_all_contract_types(self) -> List[Dict[str, Any]]:
        """Fetch all contract types from Neo4j."""
        query = """
        MATCH (c:ContractType)
        RETURN c.name as name, c.display_name as display_name
        ORDER BY c.name
        """
        with self.driver.get_session() as session:
            result = session.run(query)
            contracts = []
            for record in result:
                name = record["name"]
                display_name = self._get_display_name(name, record.get("display_name"))
                contracts.append({
                    "name": name,
                    "display_name": display_name
                })
            return contracts
    
    def get_contract_template(self, contract_type: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific contract template with its clauses."""
        query = """
        MATCH (c:ContractType {name: $contract_type})
        OPTIONAL MATCH (c)-[r:REQUIRES|INCLUDES]->(clause:Clause)
        WITH c, clause, type(r) as rel_type
        ORDER BY clause.order
        RETURN c.name as name, 
               c.display_name as display_name,
               collect({
                   id: clause.id,
                   text: clause.text_template,
                   type: rel_type
               }) as clauses
        """
        with self.driver.get_session() as session:
            result = session.run(query, contract_type=contract_type)
            record = result.single()
            
            if record is None:
                return None
            
            name = record["name"]
            display_name = self._get_display_name(name, record.get("display_name"))
            
            return {
                "name": name,
                "display_name": display_name,
                "clauses": [
                    clause for clause in record["clauses"] 
                    if clause.get("id") is not None
                ]
            }
    
    def get_contract_requirements(self, contract_type: str) -> Optional[Dict[str, Any]]:
        """
        Fetch contract requirements including REQUIRES, RECOMMENDED, OPTIONAL fields
        and DEPENDS_ON relationships.
        """
        query = """
        MATCH (c:ContractType {name: $contract_type})
        OPTIONAL MATCH (c)-[:REQUIRES]->(req:Field)
        OPTIONAL MATCH (c)-[:RECOMMENDED]->(rec:Field)
        OPTIONAL MATCH (c)-[:OPTIONAL]->(opt:Field)
        WITH c, 
             collect(DISTINCT {id: req.id, name: req.name, description: req.description}) as requires,
             collect(DISTINCT {id: rec.id, name: rec.name, description: rec.description}) as recommended,
             collect(DISTINCT {id: opt.id, name: opt.name, description: opt.description}) as optional
        
        OPTIONAL MATCH (f1:Field)-[:DEPENDS_ON]->(f2:Field)
        WHERE f1.id IN [r IN requires | r.id] OR f1.id IN [r IN recommended | r.id]
        WITH c, requires, recommended, optional,
             collect(DISTINCT {from_id: f1.id, to_id: f2.id, from_name: f1.name, to_name: f2.name}) as dependencies
        
        RETURN c.name as name,
               c.display_name as display_name,
               requires,
               recommended,
               optional,
               dependencies
        """
        with self.driver.get_session() as session:
            result = session.run(query, contract_type=contract_type)
            record = result.single()
            
            if record is None:
                return None
            
            name = record["name"]
            display_name = self._get_display_name(name, record.get("display_name"))
            
            # Filter out null entries
            requires = [r for r in record["requires"] if r.get("id") is not None]
            recommended = [r for r in record["recommended"] if r.get("id") is not None]
            optional = [r for r in record["optional"] if r.get("id") is not None]
            dependencies = [d for d in record["dependencies"] if d.get("from_id") is not None]
            
            return {
                "name": name,
                "display_name": display_name,
                "requires": requires,
                "recommended": recommended,
                "optional": optional,
                "dependencies": dependencies
            }


# Singleton instance for dependency injection
contract_repository = ContractRepository()


def get_contract_repository() -> ContractRepository:
    """
    Dependency injection helper for FastAPI.
    
    Returns:
        ContractRepository: The singleton repository instance
    """
    return contract_repository
