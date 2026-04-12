"""
Contract Generator module for GraphRAG-based legal document analysis.

This module provides the ContractGenerator class which uses Neo4j graph database
to analyze user inputs, detect missing information, and generate proactive
suggestions for legal contract creation.

The system uses a knowledge graph of legal requirements with:
- REQUIRES relationships (mandatory fields)
- RECOMMENDED relationships (suggested fields)
- OPTIONAL relationships (optional fields)
- DEPENDS_ON relationships (field dependencies)
"""
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from app.core.logger import get_logger
from app.utils.db import neo4j_driver
from app.services.legal_analysis_service import get_legal_analysis_service

logger = get_logger(__name__)


class ContractType(Enum):
    """Supported contract types in the system."""
    HIZMET_SOZLESMESI = "hizmet_sozlesmesi"
    KIRA_SOZLESMESI   = "kira_sozlesmesi"
    SATIS_SOZLESMESI  = "satis_sozlesmesi"
    BORC_SOZLESMESI   = "borc_sozlesmesi"
    IS_SOZLESMESI     = "is_sozlesmesi"
    VEKALETNAME       = "vekaletname"
    TAAHHUTNAME       = "taahhutname"


class NecessityLevel(Enum):
    """Necessity levels for contract fields."""
    REQUIRES = "REQUIRES"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"


@dataclass
class ContractField:
    """Represents a single field/requirement in a contract."""
    node_id: int
    name: str
    necessity: NecessityLevel
    description: Optional[str] = None
    depends_on: List[int] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "necessity": self.necessity.value,
            "description": self.description,
            "depends_on": self.depends_on
        }


@dataclass
class MissingFieldInfo:
    """Information about a missing field."""
    field: ContractField
    question: str
    priority: int  # 1 = highest (required), 2 = medium (recommended), 3 = low (optional)
    blocking_dependencies: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Result of the agentic reasoning analysis."""
    contract_type: str
    extracted_entities: Dict[str, Any]
    matched_fields: List[ContractField]
    missing_required: List[ContractField]
    missing_recommended: List[ContractField]
    missing_optional: List[ContractField]
    completeness_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "contract_type": self.contract_type,
            "extracted_entities": self.extracted_entities,
            "matched_fields": [f.to_dict() for f in self.matched_fields],
            "missing_required": [f.to_dict() for f in self.missing_required],
            "missing_recommended": [f.to_dict() for f in self.missing_recommended],
            "missing_optional": [f.to_dict() for f in self.missing_optional],
            "completeness_score": self.completeness_score
        }


@dataclass
class ProactiveSuggestion:
    """A proactive suggestion for the user."""
    suggestion_type: str  # "question", "reminder", "info"
    field_name: str
    message: str
    priority: int
    necessity: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.suggestion_type,
            "field_name": self.field_name,
            "message": self.message,
            "priority": self.priority,
            "necessity": self.necessity
        }


class ContractGenerator:
    """
    Main class for GraphRAG-based contract analysis and generation.
    
    Uses Neo4j knowledge graph to:
    - Fetch contract requirements based on contract type
    - Analyze extracted entities against graph requirements
    - Generate proactive suggestions for missing information
    
    Attributes:
        CONTRACT_FIELD_MAPPING: Static mapping of node IDs to field names per contract type
    """
    
    # Contract field mapping: contract_type -> {node_id: field_name}
    CONTRACT_FIELD_MAPPING: Dict[str, Dict[int, str]] = {
        ContractType.HIZMET_SOZLESMESI.value: {
            16: "İş Sahibi",
            17: "Hizmet Veren",
            18: "İşin Kapsamı",
            19: "Ücret",
            20: "Teslim Tarihi",
            21: "Gizlilik",
            22: "Fesih"
        },
        ContractType.KIRA_SOZLESMESI.value: {
            7: "Kiracı",
            8: "Kiraya Veren",
            9: "Mülk Adresi",
            10: "Kira Bedeli",
            11: "Ödeme Günü",
            12: "Depozito",
            13: "Artış Oranı",
            14: "Süre"
        },
        ContractType.SATIS_SOZLESMESI.value: {
            24: "Satıcı",
            25: "Alıcı",
            26: "Mal/Ürün",
            27: "Satış Bedeli",
            28: "Teslimat",
            29: "Ödeme Yöntemi",
            30: "Garanti"
        },
        ContractType.BORC_SOZLESMESI.value: {
            1: "Tutar",
            2: "Para Birimi",
            3: "Tarih",
            4: "Alacaklı",
            5: "Borçlu"
        }
    }
    
    # Reverse mapping for entity matching: field_name (lowercase) -> node_id
    FIELD_NAME_TO_ID: Dict[str, Dict[str, int]] = {}
    
    # Question templates for missing fields
    QUESTION_TEMPLATES: Dict[str, str] = {
        "İş Sahibi": "İş sahibinin (hizmeti satın alan taraf) adı ve soyadı nedir?",
        "Hizmet Veren": "Hizmet veren (işi yapacak taraf) kişinin/firmanın adı nedir?",
        "İşin Kapsamı": "Yapılacak işin kapsamı ve detayları nelerdir?",
        "Ücret": "Hizmet bedeli ne kadar olacak?",
        "Teslim Tarihi": "İşin teslim tarihi ne olacak?",
        "Gizlilik": "Gizlilik şartları konusunda özel bir talebiniz var mı?",
        "Fesih": "Sözleşmenin fesih koşulları neler olacak?",
        "Kiracı": "Kiracının adı ve soyadı nedir?",
        "Kiraya Veren": "Kiraya verenin (mal sahibi) adı ve soyadı nedir?",
        "Mülk Adresi": "Kiralanacak mülkün adresi nedir?",
        "Kira Bedeli": "Aylık kira bedeli ne kadar?",
        "Ödeme Günü": "Kira ödemesi ayın kaçında yapılacak?",
        "Depozito": "Depozito tutarı ne kadar olacak?",
        "Artış Oranı": "Yıllık kira artış oranı ne olacak?",
        "Süre": "Kira sözleşmesinin süresi ne kadar?",
        "Satıcı": "Satıcının adı ve soyadı nedir?",
        "Alıcı": "Alıcının adı ve soyadı nedir?",
        "Mal/Ürün": "Satılacak mal veya ürünün detayları nelerdir?",
        "Satış Bedeli": "Satış bedeli ne kadar?",
        "Teslimat": "Teslimat şartları nelerdir? (tarih, yer, şekil)",
        "Ödeme Yöntemi": "Ödeme nasıl yapılacak? (peşin, taksit, havale vb.)",
        "Garanti": "Garanti şartları nelerdir?",
        "Tutar": "Borç tutarı ne kadar?",
        "Para Birimi": "Para birimi nedir? (TRY, USD, EUR vb.)",
        "Tarih": "İşlem tarihi nedir?",
        "Alacaklı": "Alacaklının (borç veren) adı ve soyadı nedir?",
        "Borçlu": "Borçlunun adı ve soyadı nedir?"
    }
    
    # Reminder templates for recommended fields
    REMINDER_TEMPLATES: Dict[str, str] = {
        "Gizlilik": "Gizlilik maddesi eklemek sözleşmenizi güçlendirebilir.",
        "Fesih": "Fesih koşullarını belirlemek ileride olası sorunları önler.",
        "Depozito": "Depozito belirlemeniz tavsiye edilir.",
        "Artış Oranı": "Yıllık kira artış oranı belirlemek faydalı olabilir.",
        "Garanti": "Garanti koşulları eklemek alıcıyı korur."
    }
    
    def __init__(self):
        """Initialize the ContractGenerator and build reverse mappings."""
        self._build_reverse_mapping()
        self._current_analysis: Optional[AnalysisResult] = None
    
    def _build_reverse_mapping(self) -> None:
        """Build reverse mapping from field names to node IDs."""
        for contract_type, field_map in self.CONTRACT_FIELD_MAPPING.items():
            self.FIELD_NAME_TO_ID[contract_type] = {
                name.lower(): node_id for node_id, name in field_map.items()
            }
    
    def _get_field_name(self, contract_type: str, node_id: int) -> str:
        """Get field name from node ID for a contract type."""
        mapping = self.CONTRACT_FIELD_MAPPING.get(contract_type, {})
        return mapping.get(node_id, f"Field_{node_id}")
    
    def fetch_contract_requirements(
        self, 
        contract_type: str
    ) -> Dict[str, Any]:
        """
        Fetch all requirements for a contract type from Neo4j.
        
        Executes Cypher query to retrieve:
        - All nodes connected via REQUIRES relationship (mandatory)
        - All nodes connected via RECOMMENDED relationship (suggested)
        - All nodes connected via OPTIONAL relationship (optional)
        - All DEPENDS_ON relationships between field nodes
        
        Args:
            contract_type: The contract type identifier (e.g., 'kira_sozlesmesi')
            
        Returns:
            Dict containing:
                - contract_type: The queried contract type
                - requires: List of mandatory field nodes
                - recommended: List of recommended field nodes  
                - optional: List of optional field nodes
                - dependencies: List of dependency relationships
                - field_mapping: Mapping of node IDs to field names
        """
        query = """
        // Match the contract type node
        MATCH (c:ContractType {name: $contract_type})
        
        // Get REQUIRES relationships (mandatory fields)
        OPTIONAL MATCH (c)-[:REQUIRES]->(req)
        WITH c, collect(DISTINCT {
            node_id: id(req),
            name: req.name,
            description: req.description
        }) as requires_nodes
        
        // Get RECOMMENDED relationships
        OPTIONAL MATCH (c)-[:RECOMMENDED]->(rec)
        WITH c, requires_nodes, collect(DISTINCT {
            node_id: id(rec),
            name: rec.name,
            description: rec.description
        }) as recommended_nodes
        
        // Get OPTIONAL relationships
        OPTIONAL MATCH (c)-[:OPTIONAL]->(opt)
        WITH c, requires_nodes, recommended_nodes, collect(DISTINCT {
            node_id: id(opt),
            name: opt.name,
            description: opt.description
        }) as optional_nodes
        
        // Get all DEPENDS_ON relationships between field nodes
        OPTIONAL MATCH (c)-[:REQUIRES|RECOMMENDED|OPTIONAL]->(field1)
        OPTIONAL MATCH (field1)-[:DEPENDS_ON]->(field2)
        WITH c, requires_nodes, recommended_nodes, optional_nodes,
             collect(DISTINCT {
                 from_id: id(field1),
                 to_id: id(field2),
                 from_name: field1.name,
                 to_name: field2.name
             }) as dependencies
        
        RETURN 
            c.name as contract_type,
            c.display_name as display_name,
            requires_nodes,
            recommended_nodes,
            optional_nodes,
            dependencies
        """
        
        logger.debug("fetch_contract_requirements: %s", contract_type)
        try:
            with neo4j_driver.get_session() as session:
                result = session.run(query, contract_type=contract_type)
                record = result.single()

                if record is None:
                    logger.warning(
                        "fetch_contract_requirements: no graph record for %s — using static fallback",
                        contract_type,
                    )
                    return self._get_static_requirements(contract_type)

                # Process and return the graph data
                requires = [
                    ContractField(
                        node_id=r["node_id"],
                        name=r["name"] or self._get_field_name(contract_type, r["node_id"]),
                        necessity=NecessityLevel.REQUIRES,
                        description=r.get("description")
                    )
                    for r in record["requires_nodes"] if r["node_id"] is not None
                ]

                recommended = [
                    ContractField(
                        node_id=r["node_id"],
                        name=r["name"] or self._get_field_name(contract_type, r["node_id"]),
                        necessity=NecessityLevel.RECOMMENDED,
                        description=r.get("description")
                    )
                    for r in record["recommended_nodes"] if r["node_id"] is not None
                ]

                optional = [
                    ContractField(
                        node_id=r["node_id"],
                        name=r["name"] or self._get_field_name(contract_type, r["node_id"]),
                        necessity=NecessityLevel.OPTIONAL,
                        description=r.get("description")
                    )
                    for r in record["optional_nodes"] if r["node_id"] is not None
                ]

                # Process dependencies
                dependencies = [
                    d for d in record["dependencies"]
                    if d["from_id"] is not None and d["to_id"] is not None
                ]

                # Add dependencies to fields
                dep_map = {}
                for dep in dependencies:
                    from_id = dep["from_id"]
                    if from_id not in dep_map:
                        dep_map[from_id] = []
                    dep_map[from_id].append(dep["to_id"])

                for field_list in [requires, recommended, optional]:
                    for f in field_list:
                        f.depends_on = dep_map.get(f.node_id, [])

                logger.debug(
                    "fetch_contract_requirements: %s -> requires=%d recommended=%d optional=%d",
                    contract_type, len(requires), len(recommended), len(optional),
                )
                return {
                    "contract_type": contract_type,
                    "display_name": record.get("display_name", ""),
                    "requires": [f.to_dict() for f in requires],
                    "recommended": [f.to_dict() for f in recommended],
                    "optional": [f.to_dict() for f in optional],
                    "dependencies": dependencies,
                    "field_mapping": self.CONTRACT_FIELD_MAPPING.get(contract_type, {})
                }
        except Exception as e:
            logger.error(
                "fetch_contract_requirements: Neo4j query failed for %s: %s — using static fallback",
                contract_type, e, exc_info=True,
            )
            return self._get_static_requirements(contract_type)
    
    def _get_static_requirements(self, contract_type: str) -> Dict[str, Any]:
        """
        Get static requirements when graph data is not available.
        Uses the predefined CONTRACT_FIELD_MAPPING.
        """
        field_mapping = self.CONTRACT_FIELD_MAPPING.get(contract_type, {})
        
        # Default: first few fields are required, rest are recommended/optional
        requires = []
        recommended = []
        
        node_ids = sorted(field_mapping.keys())
        required_count = max(1, len(node_ids) * 2 // 3)  # First 2/3 are required
        
        for i, node_id in enumerate(node_ids):
            field = ContractField(
                node_id=node_id,
                name=field_mapping[node_id],
                necessity=NecessityLevel.REQUIRES if i < required_count else NecessityLevel.RECOMMENDED,
                description=None,
                depends_on=[]
            )
            if i < required_count:
                requires.append(field)
            else:
                recommended.append(field)
        
        return {
            "contract_type": contract_type,
            "display_name": self._get_contract_display_name(contract_type),
            "requires": [f.to_dict() for f in requires],
            "recommended": [f.to_dict() for f in recommended],
            "optional": [],
            "dependencies": [],
            "field_mapping": field_mapping
        }
    
    def _get_contract_display_name(self, contract_type: str) -> str:
        """Get human-readable contract type name."""
        display_names = {
            "hizmet_sozlesmesi": "Hizmet Sözleşmesi",
            "kira_sozlesmesi": "Kira Sözleşmesi",
            "satis_sozlesmesi": "Satış Sözleşmesi",
            "borc_sozlesmesi": "Borç Sözleşmesi"
        }
        return display_names.get(contract_type, contract_type)
    
    def agentic_reasoning_engine(
        self,
        extracted_entities: Dict[str, Any],
        graph_data: Dict[str, Any]
    ) -> AnalysisResult:
        """
        Compare spaCy extracted entities with graph requirements.
        
        This method implements the core reasoning logic:
        1. Parse the extracted entities from spaCy NLP
        2. Match entities to required/recommended/optional fields
        3. Identify missing mandatory fields
        4. Calculate completeness score
        5. Store analysis result for suggestion generation
        
        Args:
            extracted_entities: Dictionary of entities extracted by spaCy
                Example: {
                    "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
                    "MONEY": ["5000 TL"],
                    "DATE": ["01.03.2024"],
                    "ORG": ["ABC Şirketi"],
                    "LOC": ["İstanbul, Kadıköy"]
                }
            graph_data: Output from fetch_contract_requirements()
        
        Returns:
            AnalysisResult containing matched/missing fields and completeness score
        """
        contract_type = graph_data.get("contract_type", "")
        field_mapping = graph_data.get("field_mapping", {})
        
        # Reconstruct ContractField objects from graph data
        requires = [
            ContractField(
                node_id=f["node_id"],
                name=f["name"],
                necessity=NecessityLevel.REQUIRES,
                description=f.get("description"),
                depends_on=f.get("depends_on", [])
            )
            for f in graph_data.get("requires", [])
        ]
        
        recommended = [
            ContractField(
                node_id=f["node_id"],
                name=f["name"],
                necessity=NecessityLevel.RECOMMENDED,
                description=f.get("description"),
                depends_on=f.get("depends_on", [])
            )
            for f in graph_data.get("recommended", [])
        ]
        
        optional = [
            ContractField(
                node_id=f["node_id"],
                name=f["name"],
                necessity=NecessityLevel.OPTIONAL,
                description=f.get("description"),
                depends_on=f.get("depends_on", [])
            )
            for f in graph_data.get("optional", [])
        ]
        
        # Entity type to field mapping logic
        entity_field_mapping = self._create_entity_field_mapping(contract_type)
        
        # Track which fields are matched
        matched_fields: List[ContractField] = []
        matched_node_ids: Set[int] = set()
        
        # Match entities to fields
        for entity_type, entity_values in extracted_entities.items():
            if not entity_values:
                continue
            
            # Get possible fields for this entity type
            possible_field_names = entity_field_mapping.get(entity_type, [])
            
            for field_name in possible_field_names:
                # Find the field in requires/recommended/optional
                for field_list in [requires, recommended, optional]:
                    for field in field_list:
                        if field.name.lower() == field_name.lower() and field.node_id not in matched_node_ids:
                            matched_fields.append(field)
                            matched_node_ids.add(field.node_id)
                            break
        
        # Identify missing fields
        missing_required = [f for f in requires if f.node_id not in matched_node_ids]
        missing_recommended = [f for f in recommended if f.node_id not in matched_node_ids]
        missing_optional = [f for f in optional if f.node_id not in matched_node_ids]
        
        # Calculate completeness score
        total_required = len(requires)
        matched_required = len([f for f in matched_fields if f.necessity == NecessityLevel.REQUIRES])
        completeness_score = (matched_required / total_required * 100) if total_required > 0 else 100.0
        
        # Store analysis result
        self._current_analysis = AnalysisResult(
            contract_type=contract_type,
            extracted_entities=extracted_entities,
            matched_fields=matched_fields,
            missing_required=missing_required,
            missing_recommended=missing_recommended,
            missing_optional=missing_optional,
            completeness_score=round(completeness_score, 2)
        )
        
        return self._current_analysis
    
    def _create_entity_field_mapping(self, contract_type: str) -> Dict[str, List[str]]:
        """
        Create mapping from spaCy entity types to contract field names.
        
        This mapping helps match NLP-extracted entities to the correct
        contract fields based on semantic understanding.
        """
        # Common mappings for Turkish legal entities
        base_mapping = {
            "PERSON": [],  # Will be populated based on contract type
            "ORG": [],
            "MONEY": [],
            "DATE": [],
            "LOC": [],
            "CARDINAL": [],
            "PERCENT": [],
            "TIME": [],
            "PRODUCT": []
        }
        
        # Contract-specific mappings
        if contract_type == "hizmet_sozlesmesi":
            base_mapping["PERSON"] = ["İş Sahibi", "Hizmet Veren"]
            base_mapping["ORG"] = ["İş Sahibi", "Hizmet Veren"]
            base_mapping["MONEY"] = ["Ücret"]
            base_mapping["DATE"] = ["Teslim Tarihi"]
            
        elif contract_type == "kira_sozlesmesi":
            base_mapping["PERSON"] = ["Kiracı", "Kiraya Veren"]
            base_mapping["ORG"] = ["Kiracı", "Kiraya Veren"]
            base_mapping["MONEY"] = ["Kira Bedeli", "Depozito"]
            base_mapping["LOC"] = ["Mülk Adresi"]
            base_mapping["DATE"] = ["Ödeme Günü"]
            base_mapping["CARDINAL"] = ["Ödeme Günü", "Süre"]
            base_mapping["PERCENT"] = ["Artış Oranı"]
            
        elif contract_type == "satis_sozlesmesi":
            base_mapping["PERSON"] = ["Satıcı", "Alıcı"]
            base_mapping["ORG"] = ["Satıcı", "Alıcı"]
            base_mapping["MONEY"] = ["Satış Bedeli"]
            base_mapping["PRODUCT"] = ["Mal/Ürün"]
            base_mapping["DATE"] = ["Teslimat"]
            
        elif contract_type == "borc_sozlesmesi":
            base_mapping["PERSON"] = ["Alacaklı", "Borçlu"]
            base_mapping["ORG"] = ["Alacaklı", "Borçlu"]
            base_mapping["MONEY"] = ["Tutar"]
            base_mapping["DATE"] = ["Tarih"]
            base_mapping["CARDINAL"] = ["Para Birimi"]  # e.g., "TL", "USD"
        
        return base_mapping
    
    def generate_proactive_suggestions(
        self,
        analysis_result: Optional[AnalysisResult] = None
    ) -> Dict[str, Any]:
        """
        Generate proactive suggestions based on analysis results.
        
        Creates:
        - Questions for missing REQUIRED fields (high priority)
        - Reminders for missing RECOMMENDED fields (medium priority)
        - Info notes for missing OPTIONAL fields (low priority)
        
        Args:
            analysis_result: The analysis result from agentic_reasoning_engine.
                           If None, uses the stored _current_analysis.
        
        Returns:
            Dict containing structured suggestions for LLM consumption:
            {
                "contract_type": str,
                "completeness_score": float,
                "status": "incomplete" | "needs_review" | "complete",
                "suggestions": [
                    {
                        "type": "question" | "reminder" | "info",
                        "field_name": str,
                        "message": str,
                        "priority": int,
                        "necessity": str
                    }
                ],
                "next_action": str,
                "llm_prompt": str  # Ready-to-use prompt for LLM
            }
        """
        result = analysis_result or self._current_analysis
        
        if result is None:
            return {
                "error": "No analysis result available. Run agentic_reasoning_engine first.",
                "suggestions": [],
                "llm_prompt": ""
            }
        
        suggestions: List[ProactiveSuggestion] = []
        
        # Generate questions for missing required fields (priority 1)
        for field in result.missing_required:
            question = self.QUESTION_TEMPLATES.get(
                field.name,
                f"{field.name} bilgisini lütfen belirtin."
            )
            suggestions.append(ProactiveSuggestion(
                suggestion_type="question",
                field_name=field.name,
                message=question,
                priority=1,
                necessity="required"
            ))
        
        # Generate reminders for missing recommended fields (priority 2)
        for field in result.missing_recommended:
            reminder = self.REMINDER_TEMPLATES.get(
                field.name,
                f"{field.name} bilgisi eklemeniz tavsiye edilir."
            )
            suggestions.append(ProactiveSuggestion(
                suggestion_type="reminder",
                field_name=field.name,
                message=reminder,
                priority=2,
                necessity="recommended"
            ))
        
        # Generate info for missing optional fields (priority 3)
        for field in result.missing_optional:
            suggestions.append(ProactiveSuggestion(
                suggestion_type="info",
                field_name=field.name,
                message=f"{field.name} bilgisi isteğe bağlı olarak eklenebilir.",
                priority=3,
                necessity="optional"
            ))
        
        # Sort suggestions by priority
        suggestions.sort(key=lambda x: x.priority)
        
        # Determine status
        if result.missing_required:
            status = "incomplete"
        elif result.missing_recommended:
            status = "needs_review"
        else:
            status = "complete"
        
        # Determine next action
        if suggestions:
            if suggestions[0].suggestion_type == "question":
                next_action = f"Kullanıcıya şu soruyu sor: {suggestions[0].message}"
            else:
                next_action = f"Kullanıcıya şu hatırlatmayı yap: {suggestions[0].message}"
        else:
            next_action = "Sözleşme taslağını hazırla."
        
        # Generate LLM-ready prompt
        llm_prompt = self._generate_llm_prompt(result, suggestions, status)
        
        return {
            "contract_type": result.contract_type,
            "display_name": self._get_contract_display_name(result.contract_type),
            "completeness_score": result.completeness_score,
            "status": status,
            "matched_fields_count": len(result.matched_fields),
            "missing_required_count": len(result.missing_required),
            "missing_recommended_count": len(result.missing_recommended),
            "suggestions": [s.to_dict() for s in suggestions],
            "next_action": next_action,
            "llm_prompt": llm_prompt
        }
    
    def _generate_llm_prompt(
        self,
        result: AnalysisResult,
        suggestions: List[ProactiveSuggestion],
        status: str
    ) -> str:
        """Generate a structured prompt for LLM consumption."""
        prompt_parts = []
        
        # Context
        display_name = self._get_contract_display_name(result.contract_type)
        prompt_parts.append(f"## Sözleşme Analiz Raporu: {display_name}")
        prompt_parts.append(f"\n**Tamamlanma Oranı:** %{result.completeness_score}")
        prompt_parts.append(f"**Durum:** {status}")
        
        # Matched fields
        if result.matched_fields:
            prompt_parts.append("\n### Tespit Edilen Bilgiler:")
            for field in result.matched_fields:
                prompt_parts.append(f"- ✓ {field.name}")
        
        # Missing required
        if result.missing_required:
            prompt_parts.append("\n### Eksik Zorunlu Bilgiler:")
            for field in result.missing_required:
                prompt_parts.append(f"- ✗ {field.name} (ZORUNLU)")
        
        # Missing recommended
        if result.missing_recommended:
            prompt_parts.append("\n### Eksik Önerilen Bilgiler:")
            for field in result.missing_recommended:
                prompt_parts.append(f"- ○ {field.name} (ÖNERİLEN)")
        
        # Action items
        if suggestions:
            prompt_parts.append("\n### Yapılacak İşlemler:")
            questions = [s for s in suggestions if s.suggestion_type == "question"]
            reminders = [s for s in suggestions if s.suggestion_type == "reminder"]
            
            if questions:
                prompt_parts.append("\n**Sorulacak Sorular:**")
                for i, q in enumerate(questions, 1):
                    prompt_parts.append(f"{i}. {q.message}")
            
            if reminders:
                prompt_parts.append("\n**Hatırlatmalar:**")
                for r in reminders:
                    prompt_parts.append(f"- {r.message}")
        
        # Instructions for LLM
        prompt_parts.append("\n### Talimatlar:")
        if status == "incomplete":
            prompt_parts.append("Eksik zorunlu bilgileri kullanıcıdan sırayla talep et.")
            prompt_parts.append("Her seferinde tek bir soru sor ve cevabı bekle.")
        elif status == "needs_review":
            prompt_parts.append("Zorunlu bilgiler tamam. Önerilen bilgiler için hatırlatma yap.")
            prompt_parts.append("Kullanıcı isterse devam et, istemezse sözleşmeyi hazırla.")
        else:
            prompt_parts.append("Tüm bilgiler tamam. Sözleşme taslağını hazırla.")
        
        return "\n".join(prompt_parts)
    
    def analyze_user_input(
        self,
        contract_type: str,
        extracted_entities: dict
    ) -> dict:
        """
        Main entry point for analyzing user input.
    
        Combines all steps:
        1. Fetch contract requirements from Neo4j
        2. Run agentic reasoning on extracted entities
        3. Generate proactive suggestions
        4. Enrich with legal analysis (law articles, compliance score, conflicts)
    
        Args:
            contract_type: Contract type identifier
            extracted_entities: Entities extracted from user input by NLP
    
        Returns:
            Complete analysis result with suggestions and legal references
        """
        logger.info("analyze_user_input: contract_type=%s", contract_type)

        # Step 1: Fetch requirements from graph
        graph_data = self.fetch_contract_requirements(contract_type)

        # Step 2: Run reasoning engine
        analysis = self.agentic_reasoning_engine(extracted_entities, graph_data)

        # Step 3: Generate suggestions
        suggestions = self.generate_proactive_suggestions(analysis)

        # Step 4: Legal analysis — kanun maddeleri, compliance score, conflict detection
        # matched_fields listesinden alan adlarını çıkar
        analysis_dict = analysis.to_dict()
        matched_field_names = [f["name"] for f in analysis_dict.get("matched_fields", [])]
        legal_analysis = {}
        try:
            legal_service = get_legal_analysis_service()
            legal_analysis = legal_service.analyze_contract(
                contract_type=contract_type,
                clauses=matched_field_names,
                completeness_score=analysis_dict.get("completeness_score"),
            )
        except Exception as e:
            # Legal analysis opsiyonel — hata olursa ana akışı kesmez
            logger.error(
                "analyze_user_input: legal_analysis step failed for %s: %s",
                contract_type, e, exc_info=True,
            )
            legal_analysis = {
                "error": str(e),
                "related_articles": [],
                "completeness_score": None,
                "compliance_score": 0,
                "potential_conflicts": [],
                "missing_required_fields": [],
            }

        # graph_data response'a dahil edilmiyor:
        # requires/recommended/optional zaten analysis bloğunda var
        return {
            "analysis":       analysis_dict,
            "suggestions":    suggestions,
            "legal_analysis": legal_analysis,
        }
    
    def to_json(self, data: Dict[str, Any], pretty: bool = True) -> str:
        """Convert result to JSON string for LLM consumption."""
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)


# Singleton instance
contract_generator = ContractGenerator()


def get_contract_generator() -> ContractGenerator:
    """
    Dependency injection helper for FastAPI.
    
    Returns:
        ContractGenerator: The singleton instance
    """
    return contract_generator