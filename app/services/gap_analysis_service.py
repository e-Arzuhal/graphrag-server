from typing import Dict, List, Any

from app.core.logger import get_logger
from app.data.contract_schemas import CONTRACT_SCHEMAS

logger = get_logger(__name__)


def _detect_present_fields(
    contract_type: str,
    extracted_entities: Dict[str, List[str]]
) -> List[str]:
    """
    Maps spaCy entity lists to semantic field names.
    A field is 'present' only if the corresponding spaCy label has at least one value.
    """
    present = []
    persons   = extracted_entities.get("PERSON", [])
    orgs      = extracted_entities.get("ORG", [])
    money     = extracted_entities.get("MONEY", [])
    dates     = extracted_entities.get("DATE", [])
    locs      = extracted_entities.get("LOC", [])
    cardinals = extracted_entities.get("CARDINAL", [])
    percents  = extracted_entities.get("PERCENT", [])

    all_parties = persons + orgs

    if contract_type == "borc_sozlesmesi":
        if len(all_parties) >= 1: present.append("taraf_alacakli")
        if len(all_parties) >= 2: present.append("taraf_borclu")
        if money:                  present.append("borc_tutari")
        if dates:                  present.append("baslangic_tarihi")
        if percents:               present.append("faiz_orani")
        if cardinals:              present.append("vade")

    elif contract_type == "is_sozlesmesi":
        if len(all_parties) >= 1: present.append("taraf_isci")
        if len(all_parties) >= 2: present.append("taraf_isveren")
        if money:                  present.append("ucret")
        if dates:                  present.append("baslangic_tarihi")
        if len(dates) >= 2:       present.append("bitis_tarihi")
        if locs:                   present.append("calisma_yeri")
        for c in cardinals:
            if "hafta" in c:       present.append("ihbar_suresi")
            elif "ay" in c:        present.append("deneme_suresi")
            elif "yıl" in c:       present.append("sure")

    elif contract_type == "kira_sozlesmesi":
        if len(all_parties) >= 1: present.append("taraf_kiraci")
        if len(all_parties) >= 2: present.append("taraf_kiraya_veren")
        if money:                  present.append("kira_bedeli")
        if dates:                  present.append("baslangic_tarihi")
        if len(dates) >= 2:       present.append("bitis_tarihi")
        if locs:                   present.append("kiralanan_adres")
        if percents:               present.append("artis_orani")
        if cardinals:              present.append("sure")

    elif contract_type == "satis_sozlesmesi":
        if len(all_parties) >= 1: present.append("taraf_alici")
        if len(all_parties) >= 2: present.append("taraf_satici")
        if money:                  present.append("satis_bedeli")
        if dates:                  present.append("teslim_tarihi")
        if locs:                   present.append("teslim_yeri")

    elif contract_type == "hizmet_sozlesmesi":
        if len(all_parties) >= 1: present.append("taraf_1")
        if len(all_parties) >= 2: present.append("taraf_2")
        if money:                  present.append("hizmet_bedeli")
        if dates:                  present.append("baslangic_tarihi")
        if cardinals:              present.append("sure")

    elif contract_type == "vekaletname":
        if len(all_parties) >= 1: present.append("muvekkil")
        if len(all_parties) >= 2: present.append("vekil")
        if dates:                  present.append("baslangic_tarihi")

    elif contract_type == "kefalet_sozlesmesi":
        if len(all_parties) >= 1: present.append("kefil")
        if len(all_parties) >= 2: present.append("alacakli")
        if money:                  present.append("kefalet_miktari")
        if dates:                  present.append("baslangic_tarihi")

    else:  # taahhutname and unknown
        if len(all_parties) >= 1: present.append("taraf_1")
        if len(all_parties) >= 2: present.append("taraf_2")
        if dates:                  present.append("baslangic_tarihi")

    return list(set(present))


def run_gap_analysis(
    contract_type: str,
    extracted_entities: Dict[str, List[str]]
) -> Dict[str, Any]:
    schema   = CONTRACT_SCHEMAS.get(contract_type, {"required_fields": [], "optional_fields": []})
    required = schema["required_fields"]
    optional = schema["optional_fields"]
    present  = _detect_present_fields(contract_type, extracted_entities)

    missing_required = [f for f in required if f not in present]
    missing_optional = [f for f in optional if f not in present]

    if not required:
        completeness_score = 1.0
    else:
        completeness_score = round(len([f for f in required if f in present]) / len(required), 2)

    logger.info(
        "gap_analysis: contract_type=%s present=%d missing_required=%d missing_optional=%d completeness=%.2f",
        contract_type, len(present), len(missing_required), len(missing_optional), completeness_score,
    )

    return {
        "present":            present,
        "missing_required":   missing_required,
        "missing_optional":   missing_optional,
        "completeness_score": completeness_score,
    }


def needs_llm_analysis(
    missing_required: List[str],
    validation_errors: List[Dict],
) -> bool:
    """Returns True if Gemini should be called."""
    return bool(missing_required) or bool(validation_errors)
