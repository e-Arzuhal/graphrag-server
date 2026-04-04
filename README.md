# e-Arzuhal GraphRAG Server

Neo4j bilgi grafiği ve Gemini LLM tabanlı Türk sözleşme analiz servisi.  
NLP sunucusundan gelen spaCy entity verisini alır; eksik alanları, TBK ihlallerini ve hukuki riskleri tespit eder.

---

## Genel Bakış

```
Main Server
    │  POST /api/v1/analyze/input
    │  { contract_type, extracted_entities (spaCy format) }
    ▼
GraphRAG Server
    ├── 1. Gap Analysis          → eksik alanlar + completeness score
    ├── 2. Validation Rules      → TBK kural ihlalleri (ör. deneme_suresi > 2 ay)
    ├── 3. Decision Gate         → LLM gerekiyor mu?
    ├── 4. Neo4j Query           → eksik alanlar için graph verisi (conditional)
    ├── 5. Gemini 2.0 Flash      → hukuki risk analizi + TBK maddeleri (conditional)
    └── 6. Response              → analiz + chatbot soruları + hukuki değerlendirme
    ▼
Main Server → UI
```

---

## Aktif Endpoint'ler

| Method | Path | Açıklama |
|--------|------|----------|
| `POST` | `/api/v1/analyze/input` | Ana analiz endpoint'i |
| `POST` | `/api/v1/legal-analysis/contract-legal-analysis` | Kanun maddesi karşılaştırması |
| `GET`  | `/api/v1/legal-analysis/contract-graph/{type}` | Sözleşme graph yapısı |
| `GET`  | `/api/v1/legal-analysis/contract-types` | Desteklenen sözleşme tipleri |
| `GET`  | `/` | Servis durumu |
| `GET`  | `/health` | Neo4j bağlantı durumu |

---

## Desteklenen Sözleşme Tipleri

`is_sozlesmesi` · `kira_sozlesmesi` · `satis_sozlesmesi` · `hizmet_sozlesmesi` · `vekaletname` · `taahhutname` · `kefalet_sozlesmesi`

---

## Proje Yapısı

```
graphrag-server/
├── app/
│   ├── main.py                          # FastAPI app, CORS, lifespan
│   ├── config.py                        # Pydantic settings (.env okuma)
│   ├── api/
│   │   └── routes/
│   │       ├── graphrag.py              # POST /api/v1/analyze/input
│   │       └── legal_analysis.py        # /api/v1/legal-analysis/*
│   ├── data/                            # Statik veri katmanı (Neo4j gerektirmez)
│   │   ├── contract_schemas.py          # Sözleşme tipi başına zorunlu/opsiyonel alanlar
│   │   ├── field_tbk_mapping.py         # Alan → TBK maddesi + Neo4j keyword + risk seviyesi
│   │   └── question_templates.py        # Chatbot soruları
│   ├── services/
│   │   ├── gap_analysis_service.py      # spaCy entity → semantik alan eşleme + skor
│   │   ├── validation_service.py        # TBK kural kontrolleri
│   │   ├── neo4j_service.py             # Alan bazlı graph verisi çekme (async)
│   │   ├── gemini_service.py            # Gemini 2.0 Flash entegrasyonu
│   │   ├── legal_analysis_service.py    # /legal-analysis endpoint'leri için
│   │   ├── contract_generator.py        # Eski GraphRAG reasoning motoru (korunuyor)
│   │   └── contract_types.py            # ContractType enum + fallback veriler
│   ├── models/
│   │   └── response/
│   │       ├── graphrag.py              # AnalyzeInputRequest ve DTO'lar
│   │       └── contract.py              # Sözleşme DTO'ları
│   ├── db/
│   │   └── repositories/
│   │       └── contract_repository.py   # Neo4j sorguları (legal_analysis için)
│   └── utils/
│       └── db.py                        # Neo4j singleton driver
└── tests/
    └── test_analyze_pipeline.py         # 25 test (unit + integration)
```

---

## Pipeline Detayları

### 1. Gap Analysis — `app/services/gap_analysis_service.py`

spaCy entity listelerini semantik alan adlarına dönüştürür.

```
PERSON[0] + ORG[0]  →  taraf_isci / taraf_isveren
MONEY               →  ucret / kira_bedeli / satis_bedeli
DATE[0]             →  baslangic_tarihi
LOC                 →  calisma_yeri / kiralanan_adres
CARDINAL "ay"       →  deneme_suresi
CARDINAL "hafta"    →  ihbar_suresi
```

Çıktı: `present`, `missing_required`, `missing_optional`, `completeness_score`

### 2. Validation — `app/services/validation_service.py`

| Kural | TBK Maddesi |
|-------|-------------|
| `deneme_suresi > 2 ay` | TBK m.393 |
| `ihbar_suresi < 2 hafta` | TBK m.432 |

### 3. Neo4j — `app/services/neo4j_service.py`

Eksik alanların `neo4j_keywords` değerleriyle (`field_tbk_mapping.py`) graph'ta eşleşen düğüm ve ilişkileri çeker.  
Mevcut sync driver, `asyncio.run_in_executor` ile async uyumlu hale getirilmiştir.

### 4. Gemini — `app/services/gemini_service.py`

Model: `gemini-2.0-flash`  
Prompt içeriği:
- TBK graph schema (node ve ilişki tipleri)
- Eksik/mevcut alanlar
- Validation hataları
- Neo4j graph verisi

Çıktı: `tbk_articles`, `risks[]`, `general_assessment`, `compliance_penalty`  
Gemini başarısız olursa fallback ile her eksik zorunlu alan için HIGH risk döner.

---

## POST /api/v1/analyze/input

### İstek

```json
{
  "contract_type": "is_sozlesmesi",
  "extracted_entities": {
    "PERSON":   ["Ahmet Yılmaz"],
    "ORG":      ["ABC A.Ş."],
    "MONEY":    ["25.000 TL"],
    "DATE":     ["01.03.2025"],
    "LOC":      [],
    "CARDINAL": ["2 ay"],
    "PERCENT":  []
  }
}
```

### Yanıt

```json
{
  "analysis": {
    "contract_type":      "is_sozlesmesi",
    "completeness_score": 67.0,
    "compliance_score":   52.0,
    "needs_llm_analysis": true,
    "matched_fields":     ["taraf_isci", "taraf_isveren", "ucret", "baslangic_tarihi", "deneme_suresi"],
    "missing_required":   ["is_tanimi", "calisma_yeri"],
    "missing_optional":   ["sure", "ihbar_suresi", "bitis_tarihi"],
    "validation_errors":  []
  },
  "suggestions": {
    "status":      "incomplete",
    "next_action": "Çalışanın pozisyonu ve görev tanımı nedir?",
    "chatbot_questions": [
      { "priority": 1, "field": "is_tanimi",   "question": "Çalışanın pozisyonu ve görev tanımı nedir?", "required": true },
      { "priority": 2, "field": "calisma_yeri","question": "İş yerinin adresi nedir?", "required": true },
      { "priority": 3, "field": "sure",        "question": "Sözleşmenin süresi nedir?", "required": false }
    ]
  },
  "legal_analysis": {
    "tbk_articles": [393, 419],
    "risks": [
      {
        "field":       "is_tanimi",
        "risk_level":  "HIGH",
        "tbk_article": 393,
        "explanation": "İş tanımı eksik olduğunda işverenin yükümlülükleri belirsiz kalır.",
        "suggestion":  "Pozisyon ve görev tanımını sözleşmeye ekleyin."
      }
    ],
    "general_assessment": "Sözleşmede 2 zorunlu alan eksik...",
    "compliance_penalty": 0.15
  },
  "graph_data": {}
}
```

### Hata Durumları

| Kod | Sebep |
|-----|-------|
| `400` | Geçersiz `contract_type` |
| `500` | Sunucu hatası |

---

## POST /api/v1/legal-analysis/contract-legal-analysis

> Header: `X-Internal-API-Key: <INTERNAL_API_KEY>`  
> Yalnızca Main Server (Java) tarafından çağrılır.

### İstek

```json
{
  "contract_type": "kira_sozlesmesi",
  "clauses": ["Kiracı", "Kiraya Veren", "Kira Bedeli", "Mülk Adresi"],
  "metadata": { "source": "main-server" }
}
```

### Yanıt

```json
{
  "contract_type":    "kira_sozlesmesi",
  "display_name":     "Kira Sözleşmesi",
  "related_articles": [
    {
      "article_id":    "TBK-299",
      "law_name":      "Türk Borçlar Kanunu",
      "article_number":"Madde 299",
      "summary":       "Kira sözleşmesinin tanımı...",
      "relevance_score": 1.0
    }
  ],
  "compliance_score":           66.7,
  "potential_conflicts":        [],
  "suggested_missing_articles": ["'Süre' alanı için ilgili kanun maddelerini inceleyin."],
  "missing_required_fields":    ["Süre"]
}
```

---

## Kurulum

### Gereksinimler

- Python 3.10+
- Neo4j 5.x
- Gemini API key (google.ai üzerinden)

### Paket Kurulumu

```bash
conda activate arzuhal
pip install -e .
pip install -e ".[dev]"   # testler için
```

### `.env` Yapılandırması

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

APP_NAME=e-Arzuhal GraphRAG API
APP_VERSION=1.0.0
DEBUG=true

INTERNAL_API_KEY=your_internal_key
GEMINI_API_KEY=your_gemini_api_key

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:19006
```

### Çalıştırma

```bash
uvicorn app.main:app --reload --port 8000
```

`DEBUG=true` iken dokümantasyon açılır:
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

---

## Test

```bash
pytest
```

```
25 passed in 1.78s
```

Test kapsamı:
- `TestGapAnalysisService` — 8 unit test (alan eşleme, skor hesaplama, LLM karar kapısı)
- `TestValidationService` — 7 unit test (TBK kural ihlalleri)
- `TestAnalyzeInputEndpoint` — 8 integration test (Neo4j ve Gemini mock'lu)
- `TestHealthEndpoints` — 2 test

---

## Neo4j Veri Modeli

Beklenen düğüm ve ilişkiler (`legal_analysis` servisi için):

```
(:ContractType {name, display_name})
(:Field {name, description})
(:LegalArticle {article_id, law_name, article_number, summary, ...})

(:ContractType)-[:REQUIRES]->(:Field)
(:ContractType)-[:RECOMMENDED]->(:Field)
(:ContractType)-[:OPTIONAL]->(:Field)
(:Field)-[:DEPENDS_ON]->(:Field)
(:ContractType)-[:GOVERNED_BY]->(:LegalArticle)
```

`gap_analysis` + `gemini` servisleri için ek beklenti:

```
(:Node {id, name, type, description, madde_no})
— node tipleri: KAVRAM, ROL, YUKUMLULUK, HAK, SOZLESME_TIPI,
                SURE, UCRET, BORC, SORUMLULUK, TAZMINAT, FORM
```

---

