# e-Arzuhal GraphRAG Server

Neo4j tabanlı bilgi grafiği ile sözleşme analizi yapan FastAPI servisidir. Bu servis, NLP katmanından gelen entity verisini değerlendirir, eksik alanları tespit eder, proaktif soru/hatırlatma üretir ve main-server tarafından tüketilen hukuki analiz çıktıları döner.

## Genel Bakış

Sistem iki ana iş akışına sahiptir:

1. GraphRAG input analizi (`/api/v1/analyze/input`)
2. Hukuki analiz ve graph sorguları (`/api/v1/legal-analysis/*`)

Temel akış:

```text
Client -> Main Server -> NLP Server -> Main Server -> GraphRAG Server -> Main Server -> Client
```

## Mimari ve Business Logic

### 1. `ContractGenerator` akışı

Kod: `app/services/contract_generator.py`

Bu servis, `POST /api/v1/analyze/input` endpoint'inin çekirdeğidir.

Adımlar:

1. `fetch_contract_requirements(contract_type)`
2. `agentic_reasoning_engine(extracted_entities, graph_data)`
3. `generate_proactive_suggestions(analysis_result)`
4. `analyze_user_input(...)` içinde hepsini birleştirip tek JSON döndürme

Ne yapar:

- Neo4j'den `REQUIRES`, `RECOMMENDED`, `OPTIONAL`, `DEPENDS_ON` ilişkilerini çeker.
- spaCy entity tiplerini alanlara eşler (örnek: `PERSON -> Kiracı/Kiraya Veren`).
- Eşleşen ve eksik alanları çıkarır.
- `completeness_score` hesaplar (zorunlu alan kapsama oranı).
- Eksik zorunlu alanlar için soru, önerilen alanlar için hatırlatma üretir.
- LLM'e doğrudan verilecek `llm_prompt` üretir.

Neo4j'de veri yoksa statik eşlemeye fallback yapar.

### 2. `LegalAnalysisService` akışı

Kod: `app/services/legal_analysis_service.py`

Bu servis, `POST /api/v1/legal-analysis/contract-legal-analysis` ve `GET /api/v1/legal-analysis/contract-graph/{contract_type}` endpoint'lerini besler.

Ne yapar:

- Sözleşme tipini doğrular (`app/services/contract_types.py`).
- Neo4j'den zorunlu alanları ve ilgili kanun maddelerini çeker.
- Girdi olarak gelen `clauses` listesine göre eksik zorunlu alanları çıkarır.
- `compliance_score` (0-100) hesaplar.
- Basit kural tabanlı çatışma/risk analizi üretir.
- `LegalArticle` düğümü yoksa `FALLBACK_LAW_ARTICLES` ile güvenli fallback döner.

## Aktif Endpoint'ler

Not: Kod tabanında eski `contract template` model ve test dosyaları bulunsa da, aktif route kaydı yalnızca `graphrag` ve `legal_analysis` router'larıdır (`app/main.py`).

### Health

1. `GET /`
2. `GET /health`

### GraphRAG Analysis

1. `POST /api/v1/analyze/input`

### Legal Analysis

1. `POST /api/v1/legal-analysis/contract-legal-analysis`
2. `GET /api/v1/legal-analysis/contract-graph/{contract_type}`
3. `GET /api/v1/legal-analysis/contract-types`

## Endpoint Input/Output Detayları

### `GET /`

Input: yok

Output:

```json
{
  "status": "healthy",
  "message": "e-Arzuhal GraphRAG Server is running"
}
```

### `GET /health`

Input: yok

Output:

```json
{
  "status": "healthy",
  "components": {
    "server": "running",
    "neo4j": "connected"
  },
  "version": "1.0.0"
}
```

Not: Neo4j hatasında `status` değeri `degraded` olur.

### `POST /api/v1/analyze/input`

Input (`AnalyzeInputRequest`):

```json
{
  "contract_type": "kira_sozlesmesi",
  "extracted_entities": {
    "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
    "MONEY": ["5000 TL", "15000 TL"],
    "LOC": ["Kadikoy Moda Caddesi No:15"],
    "DATE": ["01.03.2026"]
  }
}
```

Output (`FullAnalysisResponse`):

```json
{
  "analysis": {
    "contract_type": "kira_sozlesmesi",
    "extracted_entities": {
      "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
      "MONEY": ["5000 TL", "15000 TL"],
      "LOC": ["Kadikoy Moda Caddesi No:15"],
      "DATE": ["01.03.2026"]
    },
    "matched_fields": [
      {"node_id": 7, "name": "Kiracı", "necessity": "REQUIRES", "description": null, "depends_on": []}
    ],
    "missing_required": [
      {"node_id": 11, "name": "Ödeme Günü", "necessity": "REQUIRES", "description": null, "depends_on": []}
    ],
    "missing_recommended": [
      {"node_id": 13, "name": "Artış Oranı", "necessity": "RECOMMENDED", "description": null, "depends_on": []}
    ],
    "missing_optional": [],
    "completeness_score": 62.5
  },
  "suggestions": {
    "contract_type": "kira_sozlesmesi",
    "display_name": "Kira Sözleşmesi",
    "completeness_score": 62.5,
    "status": "incomplete",
    "matched_fields_count": 5,
    "missing_required_count": 2,
    "missing_recommended_count": 1,
    "suggestions": [
      {
        "type": "question",
        "field_name": "Ödeme Günü",
        "message": "Kira ödemesi ayın kaçında yapılacak?",
        "priority": 1,
        "necessity": "required"
      }
    ],
    "next_action": "Kullanıcıya şu soruyu sor: Kira ödemesi ayın kaçında yapılacak?",
    "llm_prompt": "## Sözleşme Analiz Raporu: Kira Sözleşmesi..."
  },
  "graph_data": {
    "contract_type": "kira_sozlesmesi",
    "display_name": "Kira Sözleşmesi",
    "requires": [],
    "recommended": [],
    "optional": [],
    "dependencies": [],
    "field_mapping": {
      "7": "Kiracı"
    }
  }
}
```

Hata durumları:

1. `400`: Geçersiz `contract_type` (`borc_sozlesmesi`, `kira_sozlesmesi`, `hizmet_sozlesmesi`, `satis_sozlesmesi` dışı)
2. `500`: Analiz sırasında beklenmeyen hata

### `POST /api/v1/legal-analysis/contract-legal-analysis`

Header:

1. `X-Internal-API-Key: <value>`

Not: `INTERNAL_API_KEY` env var set ise zorunludur; set değilse doğrulama atlanır.

Input (`ContractLegalAnalysisRequest`):

```json
{
  "contract_type": "kira_sozlesmesi",
  "clauses": ["Kiracı", "Kiraya Veren", "Kira Bedeli", "Mülk Adresi"],
  "metadata": {
    "source": "main-server"
  }
}
```

Output (`ContractLegalAnalysisResponse`):

```json
{
  "contract_type": "kira_sozlesmesi",
  "display_name": "Kira Sözleşmesi",
  "related_articles": [
    {
      "article_id": "TBK-299",
      "law_name": "Türk Borçlar Kanunu",
      "article_number": "Madde 299",
      "summary": "Kira sözleşmesinin tanımı ve kiraya verenin temel borcu.",
      "legal_topics": ["kira", "kullanım hakkı"],
      "obligations": ["Kiraya veren, kiralananı kullanıma hazır teslim etmek zorundadır."],
      "penalties": ["Eksik teslim halinde kiracı indirim talep edebilir."],
      "references": ["TBK-301", "TBK-343"],
      "relevance_score": 1.0
    }
  ],
  "compliance_score": 66.7,
  "potential_conflicts": [],
  "suggested_missing_articles": [
    "'Süre' alanı için ilgili kanun maddelerini inceleyin."
  ],
  "missing_required_fields": ["Süre"]
}
```

Hata durumları:

1. `400`: Geçersiz `contract_type`
2. `401`: Eksik/yanlış `X-Internal-API-Key`
3. `500`: Analiz hatası

### `GET /api/v1/legal-analysis/contract-graph/{contract_type}`

Header:

1. `X-Internal-API-Key: <value>` (yukarıdaki kuralla aynı)

Path param:

1. `contract_type`: `borc_sozlesmesi`, `kira_sozlesmesi`, `hizmet_sozlesmesi`, `satis_sozlesmesi`, `is_sozlesmesi`, `vekaletname`, `taahhutname`

Output (`ContractGraphResponse`):

```json
{
  "contract_type": "kira_sozlesmesi",
  "display_name": "Kira Sözleşmesi",
  "mandatory_clauses": [
    {"name": "Kiracı", "description": "", "depends_on": []}
  ],
  "optional_clauses": [
    {"name": "Depozito", "description": "", "depends_on": []}
  ],
  "cross_references": [
    {"from": "Kira Bedeli", "to": "Ödeme Günü", "relationship": "DEPENDS_ON"}
  ],
  "related_risks": [
    "Depozito üst sınırı 3 aylık kira bedelidir (TBK Madde 342)."
  ],
  "law_articles": []
}
```

Hata durumları:

1. `400`: Geçersiz `contract_type`
2. `401`: Eksik/yanlış `X-Internal-API-Key`
3. `500`: Graph sorgu hatası

### `GET /api/v1/legal-analysis/contract-types`

Header:

1. `X-Internal-API-Key: <value>` (router seviyesinde kontrol edilir)

Output:

```json
[
  {"name": "borc_sozlesmesi", "display_name": "Borç Sözleşmesi"},
  {"name": "kira_sozlesmesi", "display_name": "Kira Sözleşmesi"},
  {"name": "hizmet_sozlesmesi", "display_name": "Hizmet Sözleşmesi"}
]
```

## Desteklenen Sözleşme Tipleri

`ContractGenerator` (analyze/input) için:

1. `borc_sozlesmesi`
2. `kira_sozlesmesi`
3. `hizmet_sozlesmesi`
4. `satis_sozlesmesi`

`LegalAnalysisService` için:

1. `borc_sozlesmesi`
2. `kira_sozlesmesi`
3. `hizmet_sozlesmesi`
4. `satis_sozlesmesi`
5. `is_sozlesmesi`
6. `vekaletname`
7. `taahhutname`

## Kurulum

### Gereksinimler

1. Python `3.10+`
2. Neo4j `5.x`

### Paket kurulumu

```bash
pip install -e .
```

Geliştirme bağımlılıkları:

```bash
pip install -e ".[dev]"
```

### `.env` yapılandırması

```bash
cp env.example .env
```

Önerilen `.env`:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

APP_NAME=e-Arzuhal GraphRAG API
APP_VERSION=1.0.0
DEBUG=true

# Settings modeli bu alanı bekliyor
INTERNAL_API_KEY=change_me

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:19006
```

### Çalıştırma

```bash
uvicorn app.main:app --reload --port 8000
```

Dokumantasyon endpoint'leri `DEBUG=true` iken açık olur:

1. `http://localhost:8000/docs`
2. `http://localhost:8000/redoc`
3. `http://localhost:8000/openapi.json`

### Docker

```bash
docker build -t graphrag-server .
docker run -p 8000:8000 \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=your_password_here \
  -e INTERNAL_API_KEY=change_me \
  -e ALLOWED_ORIGINS=http://localhost:3000 \
  graphrag-server
```

## Neo4j Modeli (Beklenen)

Temel düğümler:

1. `(:ContractType {name, display_name})`
2. `(:Field|:ContractField {name, description, ...})`
3. `(:LegalArticle {article_id, law_name, article_number, ...})`

Temel ilişkiler:

1. `(:ContractType)-[:REQUIRES]->(:Field|:ContractField)`
2. `(:ContractType)-[:RECOMMENDED]->(:Field|:ContractField)`
3. `(:ContractType)-[:OPTIONAL]->(:Field|:ContractField)`
4. `(:Field|:ContractField)-[:DEPENDS_ON]->(:Field|:ContractField)`
5. `(:ContractType)-[:GOVERNED_BY]->(:LegalArticle)`

## Test

```bash
pytest
```

Mevcut durumda `tests/test_contract_api.py` eski `template` route yapısına referans verir; uygulamanın aktif route yapısı ile birebir uyumlu değildir.

## Önemli Dosyalar

1. `app/main.py`: FastAPI app, CORS, router kaydı, lifespan
2. `app/api/routes/graphrag.py`: `/api/v1/analyze/input`
3. `app/api/routes/legal_analysis.py`: `/api/v1/legal-analysis/*`
4. `app/services/contract_generator.py`: GraphRAG reasoning
5. `app/services/legal_analysis_service.py`: Hukuki analiz ve graph retrieval
6. `app/services/contract_types.py`: Contract type enum, static field ve law fallback
7. `app/utils/db.py`: Neo4j singleton driver

## Lisans

MIT
