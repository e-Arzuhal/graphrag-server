import json
import re
from typing import List, Dict

from google import genai

from app.config import get_settings
from app.core.logger import get_logger
from app.services.pii_filter import sanitize_validation_errors

logger = get_logger(__name__)


def _loose_json_parse(raw: str) -> Dict:
    """
    Gemini bazen markdown çitleri, sondaki virgüller, tek tırnak veya açıklama
    metni döndürür. Bu yardımcı önce katı parse'ı dener, başarısız olursa
    yaygın LLM çıktı hatalarını temizleyip yeniden dener.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # En dıştaki obje içeriğini regex ile çek — açıklama metnini at
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    candidate = match.group(0) if match else text

    # Trailing virgülleri temizle: { "a": 1, } veya [ 1, 2, ]
    cleaned = re.sub(r",(\s*[}\]])", r"\1", candidate)
    # Tırnaksız anahtar adlarını yakala: { foo: 1 } → { "foo": 1 }
    cleaned = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', cleaned)
    # Tek tırnaklı stringleri çift tırnağa çevir (sadece basit durumlar)
    cleaned = re.sub(r"(?<![A-Za-z0-9_])'([^'\n]*?)'(?![A-Za-z0-9_])", r'"\1"', cleaned)
    return json.loads(cleaned)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client

# Graph schema injected into every prompt so Gemini understands
# node/relationship types without querying Neo4j directly.
GRAPH_SCHEMA = """
## Neo4j Knowledge Graph Schema (TBK — Türk Borçlar Kanunu)

### Node Types:
- KAVRAM: Legal concepts (e.g. İrade Beyanı, Sözleşme)
- ROL: Parties and actors (e.g. İşçi, İşveren, Kiracı)
- YUKUMLULUK: Legal obligations
- HAK: Legal rights
- SOZLESME_TIPI: Contract types
- SURE: Duration/time nodes
- UCRET: Wage/fee nodes
- BORC: Debt/obligation nodes
- SORUMLULUK: Liability nodes
- TAZMINAT: Compensation nodes
- ZAMANASIMI: Statute of limitations nodes
- FORM: Form/format requirements

### Key Relationship Types:
- GEREKTIRIR: A requires B
- SORUMLUDUR: A is liable for B
- YUKUMLULUK_VARDIR: There is an obligation for A
- HAKKI_VARDIR: A has the right to B
- ODEME_YUKUMLUDUR: A is obligated to pay
- TALEP_HAKKI_VARDIR: A has the right to claim B
- BAGLAR: A binds B
- SINIRLAR: A limits B
- DOGURUR: A gives rise to B
- SONA_ERDIRIR: A terminates B
"""


def _build_prompt(
    contract_type: str,
    present_fields: List[str],
    missing_required: List[str],
    missing_optional: List[str],
    validation_errors: List[Dict],
    neo4j_context: Dict[str, List[Dict]],
) -> str:
    neo4j_section = ""
    for field, records in neo4j_context.items():
        if records:
            neo4j_section += f"\n### Eksik alan: '{field}' için graph verisi\n"
            for r in records[:8]:
                neo4j_section += (
                    f"  {r.get('source_name')} ({r.get('source_type')}) "
                    f"--[{r.get('relation')}]--> "
                    f"{r.get('target_name')} ({r.get('target_type')})\n"
                )
                if r.get("source_description"):
                    neo4j_section += f"    ↳ {r['source_description'][:100]}\n"

    validation_section = ""
    if validation_errors:
        validation_section = "\n### Tespit Edilen Kural İhlalleri:\n"
        for err in validation_errors:
            validation_section += f"- {err['field']}: {err['issue']}\n"

    return f"""Sen Türk Borçlar Kanunu (TBK) alanında uzman bir hukuk danışmanısın.
Aşağıdaki sözleşme analizini yap ve JSON formatında yanıt ver.

{GRAPH_SCHEMA}

## Analiz Bilgileri
Sözleşme Türü: {contract_type}
Mevcut Alanlar: {', '.join(present_fields) or 'Hiçbiri'}
Eksik Zorunlu: {', '.join(missing_required) or 'Yok'}
Eksik Opsiyonel: {', '.join(missing_optional) or 'Yok'}
{validation_section}

## Neo4j Graph Verisi:
{neo4j_section or "Graph verisi bulunamadı — TBK bilginizi kullanın."}

## Görev:
Şu JSON yapısını döndür (tüm metinler Türkçe):

{{
  "tbk_articles": [madde numaraları — integer listesi],
  "risks": [
    {{
      "field": "alan_adı",
      "risk_level": "HIGH" | "MEDIUM" | "LOW",
      "tbk_article": madde_no_veya_null,
      "explanation": "Bu alanın eksikliğinin hukuki önemi",
      "suggestion": "Sözleşmeye eklenmesi gereken somut içerik"
    }}
  ],
  "general_assessment": "2-3 cümlelik genel hukuki değerlendirme",
  "compliance_penalty": 0.0
}}

compliance_penalty: HIGH×0.15 + MEDIUM×0.07 + LOW×0.03

ZORUNLU FORMAT KURALLARI:
- SADECE JSON döndür; ek metin, başlık, markdown çiti (```), yorum yazma.
- Tüm anahtarlar ve string değerler ÇİFT TIRNAK ile sarılmalı.
- Trailing virgül koyma (örn. {{"a":1,}} hatalı).
- tbk_articles sadece sayı listesi olmalı; null veya string ekleme.
"""


async def analyze_with_gemini(
    contract_type: str,
    present_fields: List[str],
    missing_required: List[str],
    missing_optional: List[str],
    validation_errors: List[Dict],
    neo4j_context: Dict[str, List[Dict]],
) -> Dict:
    safe_validation_errors = sanitize_validation_errors(validation_errors)
    prompt = _build_prompt(
        contract_type, present_fields, missing_required,
        missing_optional, safe_validation_errors, neo4j_context,
    )

    logger.info(
        "Gemini request | contract_type=%s | present=%d | missing_required=%d | missing_optional=%d | validation_errors=%d",
        contract_type, len(present_fields), len(missing_required), len(missing_optional), len(safe_validation_errors),
    )
    logger.debug("Gemini prompt length: %d chars", len(prompt))

    try:
        from google.genai import types as genai_types
        response = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                # Gemini'yi katı JSON'a kilitle — markdown çiti ve serbest metni engeller
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        raw = response.text.strip()
        try:
            result = _loose_json_parse(raw)
        except json.JSONDecodeError as parse_err:
            logger.warning(
                "Gemini JSON parse failed (%s) — first 240 chars: %r",
                parse_err, raw[:240],
            )
            raise
        logger.info(
            "Gemini response OK | risks=%d | compliance_penalty=%.2f",
            len(result.get("risks", [])), result.get("compliance_penalty", 0.0),
        )
        return result

    except Exception as e:
        logger.error("Gemini request failed: %s", e, exc_info=True)
        logger.warning(
            "Returning fallback HIGH-risk response for %d missing required fields",
            len(missing_required),
        )
        return {
            "tbk_articles": [],
            "risks": [
                {
                    "field": f,
                    "risk_level": "HIGH",
                    "tbk_article": None,
                    "explanation": f"{f} alanı eksik.",
                    "suggestion": f"{f} bilgisini ekleyin.",
                }
                for f in missing_required
            ],
            "general_assessment": "Otomatik analiz tamamlanamadı. Eksik alanları doldurun.",
            "compliance_penalty": len(missing_required) * 0.15,
        }
