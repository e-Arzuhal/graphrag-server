import asyncio
from typing import Dict, List

from app.core.logger import get_logger
from app.utils.db import neo4j_driver

logger = get_logger(__name__)


def _query_field(field: str, keywords: List[str], limit: int) -> List[Dict]:
    """Runs a synchronous Neo4j query for a single field."""
    query = """
    MATCH (n)-[r]-(m)
    WHERE any(kw IN $keywords WHERE
        toLower(n.id)   CONTAINS toLower(kw) OR
        toLower(n.name) CONTAINS toLower(kw)
    )
    RETURN
        n.name        AS source_name,
        n.type        AS source_type,
        n.description AS source_description,
        type(r)       AS relation,
        m.name        AS target_name,
        m.type        AS target_type
    LIMIT $limit
    """
    try:
        with neo4j_driver.get_session() as session:
            result = session.run(query, keywords=keywords, limit=limit)
            records = [dict(record) for record in result]
            logger.debug(
                "Neo4j query for field '%s' returned %d records (keywords=%s)",
                field, len(records), keywords,
            )
            return records
    except Exception as e:
        logger.error("Neo4j query failed for field '%s': %s", field, e, exc_info=True)
        return []


async def get_legal_context_for_fields(
    fields: List[str],
    field_mapping: dict,
    limit_per_field: int = 10
) -> Dict[str, List[Dict]]:
    """
    Fetches relevant Neo4j graph data for each problematic field.
    Runs sync driver queries in a thread pool to avoid blocking the event loop.
    """
    logger.info("Fetching Neo4j context for %d fields: %s", len(fields), fields)
    loop = asyncio.get_event_loop()
    results = {}

    for field in fields:
        mapping  = field_mapping.get(field)
        keywords = mapping.get("neo4j_keywords", [field]) if mapping else [field]

        records = await loop.run_in_executor(
            None, _query_field, field, keywords, limit_per_field
        )
        results[field] = records

    total_records = sum(len(r) for r in results.values())
    logger.info("Neo4j context fetch complete: %d total records across %d fields", total_records, len(fields))
    return results
