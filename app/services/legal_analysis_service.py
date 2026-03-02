"""
Legal Analysis Service

Implements the business logic for two new endpoints:

  POST /api/v1/legal-analysis/contract-legal-analysis
  GET  /api/v1/legal-analysis/contract-graph/{contract_type}

Both endpoints are called by main-server via GraphRagService.java.
They are NEVER called directly by frontend or chatbot — all traffic
goes through main-server (see AGENTS.md constraint).

Neo4j schema expected:
  (:ContractType {name, display_name})
    -[:REQUIRES|RECOMMENDED|OPTIONAL]->(:ContractField {name, description})
    -[:GOVERNED_BY]->(:LegalArticle {
        article_id, law_name, article_number, summary,
        legal_topics, obligations, penalties, references
     })

If LegalArticle nodes don't exist yet (only Borçlar Kanunu graph is loaded),
the service falls back to FALLBACK_LAW_ARTICLES from contract_types.py so the
endpoint always returns a useful response.
"""
from typing import Dict, List, Any, Optional
from app.utils.db import neo4j_driver
from app.services.contract_types import (
    ContractType,
    DISPLAY_NAMES,
    STATIC_FIELD_MAPPING,
    REQUIRED_FIELDS,
    FALLBACK_LAW_ARTICLES,
    LegalArticle,
)


class LegalAnalysisService:
    """
    Service for contract legal analysis and graph structure retrieval.

    Two public methods:
      - analyze_contract()  →  POST /contract-legal-analysis
      - get_contract_graph() →  GET /contract-graph/{contract_type}
    """

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def analyze_contract(
        self,
        contract_type: str,
        clauses: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a contract against the knowledge graph.

        Args:
            contract_type: Turkish identifier, e.g. "kira_sozlesmesi"
            clauses:        List of clause texts or field names present in the contract
            metadata:       Optional extra fields (ignored for now, reserved for future)

        Returns:
            {
              "contract_type": str,
              "display_name": str,
              "related_articles": [ LegalArticle.to_dict(), ... ],
              "compliance_score": float,          # 0-100
              "potential_conflicts": [ str, ... ],
              "suggested_missing_articles": [ str, ... ],
              "missing_required_fields": [ str, ... ],
            }
        """
        self._validate_contract_type(contract_type)

        # Fetch what the graph says this contract type requires
        required_fields = self._get_required_fields_from_graph(contract_type)

        # Identify missing required fields by simple name matching
        provided_names = {c.strip().lower() for c in clauses}
        missing_required = [
            f for f in required_fields
            if f.lower() not in provided_names
        ]

        # Calculate compliance score based on required field coverage
        total = len(required_fields) if required_fields else 1
        filled = total - len(missing_required)
        compliance_score = round((filled / total) * 100, 1)

        # Retrieve relevant law articles from the graph
        articles = self._get_law_articles(contract_type)

        # Detect potential conflicts (rule-based, extendable)
        conflicts = self._detect_conflicts(contract_type, clauses)

        # Suggest missing articles if compliance is below threshold
        suggested = []
        if compliance_score < 80:
            suggested = [
                f"'{f}' alanı için ilgili kanun maddelerini inceleyin."
                for f in missing_required[:3]  # top 3 only to avoid noise
            ]

        return {
            "contract_type":              contract_type,
            "display_name":               DISPLAY_NAMES.get(contract_type, contract_type),
            "related_articles":           [a.to_dict() for a in articles],
            "compliance_score":           compliance_score,
            "potential_conflicts":        conflicts,
            "suggested_missing_articles": suggested,
            "missing_required_fields":    missing_required,
        }

    def get_contract_graph(self, contract_type: str) -> Dict[str, Any]:
        """
        Return the full structured graph for a contract type.

        Used by: UI (clause selection screen), chatbot (via main-server)

        Returns:
            {
              "contract_type": str,
              "display_name": str,
              "mandatory_clauses": [ {name, description, depends_on}, ... ],
              "optional_clauses":  [ {name, description, depends_on}, ... ],
              "cross_references":  [ {from, to, relationship}, ... ],
              "related_risks":     [ str, ... ],
              "law_articles":      [ LegalArticle.to_dict(), ... ],
            }
        """
        self._validate_contract_type(contract_type)

        graph_data = self._fetch_full_graph(contract_type)
        articles   = self._get_law_articles(contract_type)
        risks      = self._get_related_risks(contract_type)

        return {
            "contract_type":   contract_type,
            "display_name":    DISPLAY_NAMES.get(contract_type, contract_type),
            "mandatory_clauses": graph_data["mandatory"],
            "optional_clauses":  graph_data["optional"],
            "cross_references":  graph_data["cross_references"],
            "related_risks":     risks,
            "law_articles":      [a.to_dict() for a in articles],
        }

    # -----------------------------------------------------------------------
    # Neo4j queries
    # -----------------------------------------------------------------------

    def _get_required_fields_from_graph(self, contract_type: str) -> List[str]:
        """
        Returns list of required field names from Neo4j.
        Falls back to REQUIRED_FIELDS static map if graph is empty.
        """
        query = """
        MATCH (c:ContractType {name: $contract_type})-[:REQUIRES]->(f)
        RETURN f.name AS name
        """
        try:
            with neo4j_driver.get_session() as session:
                result = session.run(query, contract_type=contract_type)
                names = [r["name"] for r in result if r["name"]]
                if names:
                    return names
        except Exception:
            pass

        # Fallback to static map
        field_keys = REQUIRED_FIELDS.get(contract_type, [])
        mapping    = STATIC_FIELD_MAPPING.get(contract_type, {})
        return [mapping[k] for k in field_keys if k in mapping]

    def _get_law_articles(self, contract_type: str) -> List[LegalArticle]:
        """
        Fetch LegalArticle nodes from Neo4j.
        Falls back to FALLBACK_LAW_ARTICLES if no nodes exist.
        """
        query = """
        MATCH (c:ContractType {name: $contract_type})-[:GOVERNED_BY]->(a:LegalArticle)
        RETURN
            a.article_id    AS article_id,
            a.law_name      AS law_name,
            a.article_number AS article_number,
            a.summary       AS summary,
            a.legal_topics  AS legal_topics,
            a.obligations   AS obligations,
            a.penalties     AS penalties,
            a.references    AS references
        ORDER BY a.article_number
        """
        try:
            with neo4j_driver.get_session() as session:
                result  = session.run(query, contract_type=contract_type)
                records = list(result)
                if records:
                    return [
                        LegalArticle(
                            article_id    = r["article_id"]     or "",
                            law_name      = r["law_name"]       or "",
                            article_number= r["article_number"] or "",
                            summary       = r["summary"]        or "",
                            legal_topics  = r["legal_topics"]   or [],
                            obligations   = r["obligations"]    or [],
                            penalties     = r["penalties"]      or [],
                            references    = r["references"]     or [],
                        )
                        for r in records
                    ]
        except Exception:
            pass

        # Fallback — always return something useful
        fallback_data = FALLBACK_LAW_ARTICLES.get(contract_type, [])
        return [LegalArticle(**d) for d in fallback_data]

    def _fetch_full_graph(self, contract_type: str) -> Dict[str, Any]:
        """
        Fetch full clause graph: mandatory, optional, and cross-references.
        Falls back to STATIC_FIELD_MAPPING if graph is empty.
        """
        query = """
        MATCH (c:ContractType {name: $contract_type})

        // Mandatory clauses
        OPTIONAL MATCH (c)-[:REQUIRES]->(req)
        WITH c, collect(DISTINCT {
            name: req.name,
            description: coalesce(req.description, ''),
            depends_on: []
        }) AS mandatory

        // Optional + recommended clauses
        OPTIONAL MATCH (c)-[:RECOMMENDED|OPTIONAL]->(opt)
        WITH c, mandatory, collect(DISTINCT {
            name: opt.name,
            description: coalesce(opt.description, ''),
            depends_on: []
        }) AS optional_clauses

        // Cross-references between clauses
        OPTIONAL MATCH (c)-[:REQUIRES|RECOMMENDED|OPTIONAL]->(f1)
        OPTIONAL MATCH (f1)-[rel:DEPENDS_ON]->(f2)
        WITH mandatory, optional_clauses,
             collect(DISTINCT {
                 from: f1.name,
                 to: f2.name,
                 relationship: type(rel)
             }) AS cross_refs

        RETURN mandatory, optional_clauses, cross_refs
        """
        try:
            with neo4j_driver.get_session() as session:
                result = session.run(query, contract_type=contract_type)
                record = result.single()
                if record:
                    mandatory = [c for c in record["mandatory"]       if c.get("name")]
                    optional  = [c for c in record["optional_clauses"] if c.get("name")]
                    cross_refs= [r for r in record["cross_refs"]       if r.get("from") and r.get("to")]
                    if mandatory or optional:
                        return {
                            "mandatory":        mandatory,
                            "optional":         optional,
                            "cross_references": cross_refs,
                        }
        except Exception:
            pass

        # Fallback: build from static maps
        field_keys  = REQUIRED_FIELDS.get(contract_type, [])
        mapping     = STATIC_FIELD_MAPPING.get(contract_type, {})
        all_keys    = list(mapping.keys())
        req_set     = set(field_keys)

        mandatory = [
            {"name": mapping[k], "description": "", "depends_on": []}
            for k in all_keys if k in req_set
        ]
        optional = [
            {"name": mapping[k], "description": "", "depends_on": []}
            for k in all_keys if k not in req_set
        ]
        return {
            "mandatory":        mandatory,
            "optional":         optional,
            "cross_references": [],
        }

    # -----------------------------------------------------------------------
    # Rule-based helpers
    # -----------------------------------------------------------------------

    def _detect_conflicts(
        self, contract_type: str, clauses: List[str]
    ) -> List[str]:
        """
        Simple rule-based conflict detection.
        Extend this as the knowledge graph matures.
        """
        conflicts: List[str] = []
        clause_lower = {c.lower() for c in clauses}

        if contract_type == "kira_sozlesmesi":
            # TBK-343: kira artışı TÜFE'yi aşamaz — warn if high artış oranı mentioned
            if any("artış" in c or "zam" in c for c in clause_lower):
                conflicts.append(
                    "Kira artış oranı TBK Madde 343 gereği bir önceki yılın TÜFE "
                    "oranını aşamaz. Belirtilen artış oranını kontrol edin."
                )

        if contract_type == "is_sozlesmesi":
            # İş Kanunu: deneme süresi 2 ayı geçemez
            if any("deneme" in c for c in clause_lower):
                conflicts.append(
                    "İş Kanunu Madde 15 gereği deneme süresi en fazla 2 ay olabilir."
                )

        if contract_type == "borc_sozlesmesi":
            # TBK-88: aşırı faiz yasağı
            if any("faiz" in c for c in clause_lower):
                conflicts.append(
                    "TBK Madde 88 gereği sözleşme faizi yasal faizi aşmamalıdır. "
                    "Belirtilen faiz oranını doğrulayın."
                )

        return conflicts

    def _get_related_risks(self, contract_type: str) -> List[str]:
        """
        Return known legal risks for a contract type.
        These will later come from Neo4j Risk nodes.
        """
        risk_map: Dict[str, List[str]] = {
            "kira_sozlesmesi": [
                "Depozito üst sınırı 3 aylık kira bedelidir (TBK Madde 342).",
                "Erken fesih hakkı açıkça düzenlenmemişse yasal ihbar süreleri geçerlidir.",
            ],
            "is_sozlesmesi": [
                "Yazılı sözleşme zorunluluğu — sözlü yapılırsa ispat güçlüğü doğar.",
                "Kıdem ve ihbar tazminatı hakları sözleşmeyle ortadan kaldırılamaz.",
            ],
            "borc_sozlesmesi": [
                "Resmi şekil şartı: yüksek tutarlı borç senetleri noter onayı gerektirebilir.",
                "Zaman aşımı süresi genel olarak 10 yıldır (TBK Madde 146).",
            ],
            "satis_sozlesmesi": [
                "Taşınmaz satışları resmi şekil (tapu) gerektirir; adi yazılı sözleşme yeterli değildir.",
                "Ayıp ihbar süresi gözden geçirme tarihinden itibaren 2 yıldır.",
            ],
            "hizmet_sozlesmesi": [
                "Rekabet yasağı maddesi coğrafi ve süre sınırı içermek zorundadır.",
            ],
            "vekaletname": [
                "Taşınmaz devri veya dava için özel vekâletname zorunludur.",
                "Vekâletin ölümle sona erip ermeyeceği açıkça belirtilmelidir.",
            ],
            "taahhutname": [
                "Konusu imkânsız olan taahhütler kesin hükümsüzdür (TBK Madde 27).",
            ],
        }
        return risk_map.get(contract_type, [])

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def _validate_contract_type(self, contract_type: str) -> None:
        valid = ContractType.values()
        if contract_type not in valid:
            raise ValueError(
                f"Geçersiz sözleşme tipi: '{contract_type}'. "
                f"Geçerli tipler: {valid}"
            )


# Singleton for FastAPI dependency injection
_legal_analysis_service = LegalAnalysisService()


def get_legal_analysis_service() -> LegalAnalysisService:
    return _legal_analysis_service
