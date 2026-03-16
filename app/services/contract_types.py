"""
Contract type definitions and field mappings for all supported contract types.

Extends the base ContractType enum to include all types defined in AGENTS.md:
borc_sozlesmesi, kira_sozlesmesi, hizmet_sozlesmesi, satis_sozlesmesi,
is_sozlesmesi, vekaletname, taahhutname

Also defines LegalArticle dataclass for law article references returned
by the /contract-legal-analysis endpoint.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


class ContractType(Enum):
    """All supported contract types. Turkish names used as Neo4j node keys."""
    BORC_SOZLESMESI    = "borc_sozlesmesi"
    KIRA_SOZLESMESI    = "kira_sozlesmesi"
    HIZMET_SOZLESMESI  = "hizmet_sozlesmesi"
    SATIS_SOZLESMESI   = "satis_sozlesmesi"
    IS_SOZLESMESI      = "is_sozlesmesi"
    VEKALETNAME        = "vekaletname"
    TAAHHUTNAME        = "taahhutname"

    @classmethod
    def values(cls) -> List[str]:
        return [e.value for e in cls]

    @classmethod
    def display_name(cls, value: str) -> str:
        return DISPLAY_NAMES.get(value, value)


DISPLAY_NAMES: Dict[str, str] = {
    "borc_sozlesmesi":   "Borç Sözleşmesi",
    "kira_sozlesmesi":   "Kira Sözleşmesi",
    "hizmet_sozlesmesi": "Hizmet Sözleşmesi",
    "satis_sozlesmesi":  "Satış Sözleşmesi",
    "is_sozlesmesi":     "İş Sözleşmesi",
    "vekaletname":       "Vekaletname",
    "taahhutname":       "Taahhütname",
}


# ---------------------------------------------------------------------------
# Legal article reference — returned by /contract-legal-analysis
# ---------------------------------------------------------------------------

@dataclass
class LegalArticle:
    """
    A single law article relevant to a contract type or clause.

    Populated from Neo4j LegalArticle nodes. If the node exists in the graph
    it is returned as-is. If the graph has no LegalArticle nodes yet (e.g. only
    Borçlar Kanunu is loaded), the law_name / article_number fields will still
    be populated from whatever properties are stored.
    """
    article_id: str                          # e.g. "TBK-98"
    law_name: str                            # e.g. "Türk Borçlar Kanunu"
    article_number: str                      # e.g. "Madde 98"
    summary: str                             # one-sentence plain-Turkish summary
    legal_topics: List[str] = field(default_factory=list)   # ["borç", "faiz"]
    obligations: List[str] = field(default_factory=list)    # what the article requires
    penalties: List[str] = field(default_factory=list)      # consequences of violation
    references: List[str] = field(default_factory=list)     # related article IDs
    relevance_score: float = 1.0             # 0-1, filled by scoring logic

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id":      self.article_id,
            "law_name":        self.law_name,
            "article_number":  self.article_number,
            "summary":         self.summary,
            "legal_topics":    self.legal_topics,
            "obligations":     self.obligations,
            "penalties":       self.penalties,
            "references":      self.references,
            "relevance_score": round(self.relevance_score, 3),
        }


# ---------------------------------------------------------------------------
# Static field definitions used when Neo4j has no graph data yet
# These mirror CONTRACT_FIELD_MAPPING in contract_generator.py but are
# extended with the two new contract types.
# ---------------------------------------------------------------------------

STATIC_FIELD_MAPPING: Dict[str, Dict[str, str]] = {
    "borc_sozlesmesi": {
        "tutar":       "Tutar",
        "para_birimi": "Para Birimi",
        "tarih":       "Tarih",
        "alacakli":    "Alacaklı",
        "borclu":      "Borçlu",
        "faiz_orani":  "Faiz Oranı",
        "vade":        "Vade",
    },
    "kira_sozlesmesi": {
        "kiraci":       "Kiracı",
        "kiraya_veren": "Kiraya Veren",
        "mulk_adresi":  "Mülk Adresi",
        "kira_bedeli":  "Kira Bedeli",
        "odeme_gunu":   "Ödeme Günü",
        "depozito":     "Depozito",
        "artis_orani":  "Artış Oranı",
        "sure":         "Süre",
    },
    "hizmet_sozlesmesi": {
        "is_sahibi":    "İş Sahibi",
        "hizmet_veren": "Hizmet Veren",
        "is_kapsami":   "İşin Kapsamı",
        "ucret":        "Ücret",
        "teslim_tarihi":"Teslim Tarihi",
        "gizlilik":     "Gizlilik",
        "fesih":        "Fesih",
    },
    "satis_sozlesmesi": {
        "satici":        "Satıcı",
        "alici":         "Alıcı",
        "mal_urun":      "Mal/Ürün",
        "satis_bedeli":  "Satış Bedeli",
        "teslimat":      "Teslimat",
        "odeme_yontemi": "Ödeme Yöntemi",
        "garanti":       "Garanti",
    },
    "is_sozlesmesi": {
        "isveren":          "İşveren",
        "isci":             "İşçi",
        "gorev_tanimi":     "Görev Tanımı",
        "maas":             "Maaş",
        "baslangic_tarihi": "Başlangıç Tarihi",
        "calisma_saatleri": "Çalışma Saatleri",
        "izin_suresi":      "İzin Süresi",
        "ihbar_suresi":     "İhbar Süresi",
        "deneme_suresi":    "Deneme Süresi",
    },
    "vekaletname": {
        "vekalet_veren": "Vekâlet Veren",
        "vekil":         "Vekil",
        "yetki_kapsami": "Yetki Kapsamı",
        "sure":          "Süre",
        "tarih":         "Tarih",
        "noterlik":      "Noterlik",
    },
    "taahhutname": {
        "taahhut_eden":  "Taahhüt Eden",
        "alici_taraf":   "Alıcı Taraf",
        "taahhut_konusu":"Taahhüt Konusu",
        "sure":          "Süre",
        "tarih":         "Tarih",
        "ceza_maddesi":  "Ceza Maddesi",
    },
}

# Which fields are mandatory for each contract type (used when graph is empty)
REQUIRED_FIELDS: Dict[str, List[str]] = {
    "borc_sozlesmesi":   ["tutar", "para_birimi", "alacakli", "borclu", "tarih"],
    "kira_sozlesmesi":   ["kiraci", "kiraya_veren", "mulk_adresi", "kira_bedeli", "sure"],
    "hizmet_sozlesmesi": ["is_sahibi", "hizmet_veren", "is_kapsami", "ucret"],
    "satis_sozlesmesi":  ["satici", "alici", "mal_urun", "satis_bedeli"],
    "is_sozlesmesi":     ["isveren", "isci", "gorev_tanimi", "maas", "baslangic_tarihi"],
    "vekaletname":       ["vekalet_veren", "vekil", "yetki_kapsami", "tarih"],
    "taahhutname":       ["taahhut_eden", "alici_taraf", "taahhut_konusu", "tarih"],
}

# Law article fallback: if Neo4j has no LegalArticle nodes, return these
# so the endpoint never returns an empty list.
# Keys are contract types; values are minimal article stubs.
FALLBACK_LAW_ARTICLES: Dict[str, List[Dict[str, Any]]] = {
    "borc_sozlesmesi": [
        {
            "article_id": "TBK-98",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 98",
            "summary": "Borç ilişkisinin kurulması ve tarafların temel yükümlülükleri.",
            "legal_topics": ["borç", "alacak"],
            "obligations": ["Borçlu, vadesi gelen borcu ödemekle yükümlüdür."],
            "penalties": ["Temerrüt faizi uygulanabilir."],
            "references": ["TBK-117", "TBK-120"],
            "relevance_score": 1.0,
        },
        {
            "article_id": "TBK-120",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 120",
            "summary": "Faiz oranı ve temerrüt faizine ilişkin hükümler.",
            "legal_topics": ["faiz", "temerrüt"],
            "obligations": ["Faiz oranı sözleşmede belirtilmelidir."],
            "penalties": ["Yasal faiz oranı aşılamaz."],
            "references": ["TBK-98"],
            "relevance_score": 0.9,
        },
    ],
    "kira_sozlesmesi": [
        {
            "article_id": "TBK-299",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 299",
            "summary": "Kira sözleşmesinin tanımı ve kiraya verenin temel borcu.",
            "legal_topics": ["kira", "kullanım hakkı"],
            "obligations": ["Kiraya veren, kiralananı kullanıma hazır teslim etmek zorundadır."],
            "penalties": ["Eksik teslim halinde kiracı indirim talep edebilir."],
            "references": ["TBK-301", "TBK-343"],
            "relevance_score": 1.0,
        },
        {
            "article_id": "TBK-343",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 343",
            "summary": "Kira bedelinin artırılmasına ilişkin sınırlamalar.",
            "legal_topics": ["kira artışı", "TÜFE"],
            "obligations": ["Kira artışı bir önceki kira yılındaki TÜFE oranını aşamaz."],
            "penalties": ["Aşan kısım geçersiz sayılır."],
            "references": ["TBK-299"],
            "relevance_score": 0.95,
        },
    ],
    "hizmet_sozlesmesi": [
        {
            "article_id": "TBK-393",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 393",
            "summary": "Hizmet sözleşmesinin tanımı; işçinin bağımlılık ilişkisi.",
            "legal_topics": ["hizmet", "ücret", "bağımlılık"],
            "obligations": ["İşçi, işverenin talimatlarına uymakla yükümlüdür."],
            "penalties": ["Haksız fesih tazminat yükümlülüğü doğurur."],
            "references": ["TBK-395", "TBK-404"],
            "relevance_score": 1.0,
        },
    ],
    "satis_sozlesmesi": [
        {
            "article_id": "TBK-207",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 207",
            "summary": "Satış sözleşmesinin tanımı; satıcının teslim ve devir borcu.",
            "legal_topics": ["satış", "mülkiyet devri", "teslim"],
            "obligations": ["Satıcı, satılan malı teslim etmek ve mülkiyetini devretmekle yükümlüdür."],
            "penalties": ["Ayıplı teslimde alıcı sözleşmeden dönebilir."],
            "references": ["TBK-209", "TBK-219"],
            "relevance_score": 1.0,
        },
    ],
    "is_sozlesmesi": [
        {
            "article_id": "4857-1",
            "law_name": "İş Kanunu",
            "article_number": "Madde 1",
            "summary": "İş Kanunu'nun kapsamı ve iş sözleşmesinin tanımı.",
            "legal_topics": ["iş sözleşmesi", "işçi", "işveren"],
            "obligations": ["İşveren, ücret ve çalışma koşullarını yazılı bildirmekle yükümlüdür."],
            "penalties": ["Yükümlülüklerin ihlali idari para cezasına yol açar."],
            "references": ["4857-17", "4857-25"],
            "relevance_score": 1.0,
        },
    ],
    "vekaletname": [
        {
            "article_id": "TMK-502",
            "law_name": "Türk Medeni Kanunu",
            "article_number": "Madde 502",
            "summary": "Vekâlet ilişkisinin kurulması ve vekilin yükümlülükleri.",
            "legal_topics": ["vekâlet", "temsil"],
            "obligations": ["Vekil, vekâlet verenin çıkarlarını gözetmekle yükümlüdür."],
            "penalties": ["Görevin kötüye kullanılması tazminat gerektirir."],
            "references": [],
            "relevance_score": 1.0,
        },
    ],
    "taahhutname": [
        {
            "article_id": "TBK-26",
            "law_name": "Türk Borçlar Kanunu",
            "article_number": "Madde 26",
            "summary": "Sözleşme özgürlüğü; tarafların içeriği serbestçe belirleyebileceği.",
            "legal_topics": ["taahhüt", "sözleşme özgürlüğü"],
            "obligations": ["Taahhüt edilen edim kanuna ve ahlaka aykırı olamaz."],
            "penalties": ["Aykırı taahhütler kesin hükümsüzdür."],
            "references": ["TBK-27"],
            "relevance_score": 1.0,
        },
    ],
}
