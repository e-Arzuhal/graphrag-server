from typing import List, Dict

from app.core.logger import get_logger

logger = get_logger(__name__)


def run_validations(
    contract_type: str,
    extracted_entities: Dict[str, List[str]]
) -> List[Dict]:
    errors    = []
    cardinals = extracted_entities.get("CARDINAL", [])
    logger.debug(
        "run_validations: contract_type=%s cardinals=%s", contract_type, cardinals,
    )

    if contract_type == "is_sozlesmesi":

        for c in cardinals:
            if "ay" in c:
                try:
                    num = float(''.join(ch for ch in c if ch.isdigit() or ch == '.'))
                    if num > 2:
                        errors.append({
                            "field": "deneme_suresi",
                            "issue": f"Deneme süresi {c} olarak belirlenmiş. TBK m.393 uyarınca maksimum 2 aydır.",
                            "tbk_limit": "TBK m.393 — max 2 ay"
                        })
                except ValueError:
                    logger.debug("Could not parse CARDINAL '%s' as number (ay check)", c)

            if "hafta" in c:
                try:
                    num = float(''.join(ch for ch in c if ch.isdigit() or ch == '.'))
                    if num < 2:
                        errors.append({
                            "field": "ihbar_suresi",
                            "issue": f"İhbar süresi {c} olarak belirlenmiş. TBK m.432 uyarınca minimum 2 haftadır.",
                            "tbk_limit": "TBK m.432 — min 2 hafta"
                        })
                except ValueError:
                    logger.debug("Could not parse CARDINAL '%s' as number (hafta check)", c)

    if errors:
        logger.info(
            "run_validations: %d TBK rule violation(s) for %s",
            len(errors), contract_type,
        )
    return errors
