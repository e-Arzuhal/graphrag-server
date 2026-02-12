# e-Arzuhal GraphRAG Server

Neo4j bilgi grafiği kullanarak hukuki belge oluşturma için GraphRAG (Graph-based Retrieval-Augmented Generation) sunucusu.

## 🎯 Genel Bakış

Bu modül, e-Arzuhal sisteminin **akıl yürütme motoru**dur. NLP-Server'dan gelen entity'leri Neo4j'deki hukuki bilgi grafiğiyle karşılaştırarak:

- Eksik zorunlu bilgileri tespit eder
- Proaktif sorular/öneriler üretir
- LLM'e beslenecek yapılandırılmış JSON çıktısı oluşturur

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  NLP-Server │ ──► │  GraphRAG-Server │ ──► │     LLM     │
│   (spaCy)   │     │   (Bu Modül)     │     │ (Claude/GPT)│
└─────────────┘     └──────────────────┘     └─────────────┘
```

## 🚀 Özellikler

- **Graf Tabanlı Gereksinim Analizi**: Neo4j'den sözleşme gereksinimlerini çeker
- **Akıllı Entity Eşleştirme**: NLP çıktılarını graf gereksinimleriyle karşılaştırır
- **Proaktif Soru Üretimi**: Eksik bilgiler için akıllı sorular oluşturur
- **LLM-Ready JSON Çıktısı**: Doğrudan LLM'e beslenebilir format
- **Modüler Mimari**: ContractGenerator sınıfı ile temiz kod yapısı
- **Bolt Protokolü**: Neo4j bağlantısı için performanslı iletişim

## 📦 Kurulum

### Gereksinimler

- Python 3.10+
- Neo4j 5.x (lokal veya Docker)
- NLP-Server (spaCy entity extraction için)

### Kurulum

```bash
cd graphrag-server
pip install -e .
```

### Ortam Değişkenleri

```bash
cp env.example .env
# .env dosyasını Neo4j bilgilerinizle düzenleyin
```

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Sunucuyu Başlatma

```bash
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker build -t graphrag-server .
docker run -p 8000:8000 \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=your_password \
  graphrag-server
```

## 🗺️ Schema Mapping (Node ID → Alan Adı)

Veritabanındaki sayısal ID'lerin alan adlarıyla eşleşmesi:

### Borç Sözleşmesi (IDs: 1-5)
| Node ID | Alan Adı |
|---------|----------|
| 1 | Tutar |
| 2 | Para Birimi |
| 3 | Tarih |
| 4 | Alacaklı |
| 5 | Borçlu |

### Kira Sözleşmesi (IDs: 7-14)
| Node ID | Alan Adı |
|---------|----------|
| 7 | Kiracı |
| 8 | Kiraya Veren |
| 9 | Mülk Adresi |
| 10 | Kira Bedeli |
| 11 | Ödeme Günü |
| 12 | Depozito |
| 13 | Artış Oranı |
| 14 | Süre |

### Hizmet Sözleşmesi (IDs: 16-22)
| Node ID | Alan Adı |
|---------|----------|
| 16 | İş Sahibi |
| 17 | Hizmet Veren |
| 18 | İşin Kapsamı |
| 19 | Ücret |
| 20 | Teslim Tarihi |
| 21 | Gizlilik |
| 22 | Fesih |

### Satış Sözleşmesi (IDs: 24-30)
| Node ID | Alan Adı |
|---------|----------|
| 24 | Satıcı |
| 25 | Alıcı |
| 26 | Mal/Ürün |
| 27 | Satış Bedeli |
| 28 | Teslimat |
| 29 | Ödeme Yöntemi |
| 30 | Garanti |

## 🧠 Business Logic

### ContractGenerator Sınıfı

Ana iş mantığı `app/services/contract_generator.py` içindeki `ContractGenerator` sınıfında:

#### 1. `fetch_contract_requirements(contract_type)`

Neo4j'den sözleşme gereksinimlerini çeker:

```python
# Cypher sorgusu REQUIRES, RECOMMENDED, OPTIONAL ve DEPENDS_ON ilişkilerini getirir
requirements = generator.fetch_contract_requirements("kira_sozlesmesi")
```

**Çıktı:**
```json
{
  "contract_type": "kira_sozlesmesi",
  "display_name": "Kira Sözleşmesi",
  "requires": [{"node_id": 7, "name": "Kiracı", "necessity": "REQUIRES"}],
  "recommended": [{"node_id": 12, "name": "Depozito"}],
  "optional": [],
  "dependencies": [{"from_id": 10, "to_id": 11}]
}
```

#### 2. `agentic_reasoning_engine(extracted_entities, graph_data)`

NLP-Server'dan gelen entity'leri graf gereksinimleriyle karşılaştırır:

```python
# NLP-Server'dan gelen entity'ler
extracted_entities = {
    "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
    "MONEY": ["5000 TL"],
    "LOC": ["Kadıköy, İstanbul"]
}

# Analiz
analysis = generator.agentic_reasoning_engine(extracted_entities, requirements)
```

**Çıktı:**
```json
{
  "matched_fields": ["Kiracı", "Kiraya Veren", "Kira Bedeli", "Mülk Adresi"],
  "missing_required": ["Ödeme Günü", "Süre"],
  "missing_recommended": ["Depozito", "Artış Oranı"],
  "completeness_score": 66.67
}
```

#### 3. `generate_proactive_suggestions()`

Eksik bilgiler için sorular/hatırlatmalar üretir:

```python
suggestions = generator.generate_proactive_suggestions(analysis)
```

**Çıktı:**
```json
{
  "status": "incomplete",
  "suggestions": [
    {
      "type": "question",
      "field_name": "Ödeme Günü",
      "message": "Kira ödemesi ayın kaçında yapılacak?",
      "priority": 1,
      "necessity": "required"
    },
    {
      "type": "reminder",
      "field_name": "Depozito",
      "message": "Depozito belirlemeniz tavsiye edilir.",
      "priority": 2,
      "necessity": "recommended"
    }
  ],
  "next_action": "Kullanıcıya şu soruyu sor: Kira ödemesi ayın kaçında yapılacak?",
  "llm_prompt": "## Sözleşme Analiz Raporu: Kira Sözleşmesi\n..."
}
```

### Entity → Alan Eşleştirme Mantığı

| spaCy Entity | Eşleşen Alanlar (Kira Sözleşmesi) |
|--------------|-----------------------------------|
| PERSON | Kiracı, Kiraya Veren |
| ORG | Kiracı, Kiraya Veren |
| MONEY | Kira Bedeli, Depozito |
| LOC | Mülk Adresi |
| DATE | Ödeme Günü |
| CARDINAL | Ödeme Günü, Süre |
| PERCENT | Artış Oranı |

## 📖 API Endpoints

### Sağlık Kontrolleri

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/` | Basit sağlık kontrolü |
| GET | `/health` | Detaylı sağlık durumu (Neo4j dahil) |

### Sözleşme Şablonları

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/v1/template/` | Tüm sözleşme tiplerini listele |
| GET | `/api/v1/template/{contract_type}` | Sözleşme şablonunu getir |

### GraphRAG Analiz (Yeni)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/v1/analyze/types` | Desteklenen sözleşme tiplerini listele |
| GET | `/api/v1/analyze/requirements/{contract_type}` | Graf gereksinimlerini getir |
| GET | `/api/v1/analyze/field-mapping/{contract_type}` | Alan eşlemelerini getir |
| POST | `/api/v1/analyze/input` | Kullanıcı girdisini analiz et |

### Kullanım Örnekleri

#### Sözleşme Gereksinimlerini Getir

```bash
curl http://localhost:8000/api/v1/analyze/requirements/kira_sozlesmesi
```

#### Kullanıcı Girdisini Analiz Et

```bash
curl -X POST http://localhost:8000/api/v1/analyze/input \
  -H "Content-Type: application/json" \
  -d '{
    "contract_type": "kira_sozlesmesi",
    "extracted_entities": {
      "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],
      "MONEY": ["5000 TL", "15000 TL"],
      "LOC": ["Kadıköy Moda Caddesi No:15"]
    }
  }'
```

#### Örnek API Yanıtı

```json
{
  "analysis": {
    "contract_type": "kira_sozlesmesi",
    "completeness_score": 62.5,
    "matched_fields": [
      {"node_id": 7, "name": "Kiracı", "necessity": "REQUIRES"},
      {"node_id": 8, "name": "Kiraya Veren", "necessity": "REQUIRES"},
      {"node_id": 10, "name": "Kira Bedeli", "necessity": "REQUIRES"},
      {"node_id": 12, "name": "Depozito", "necessity": "RECOMMENDED"},
      {"node_id": 9, "name": "Mülk Adresi", "necessity": "REQUIRES"}
    ],
    "missing_required": [
      {"node_id": 11, "name": "Ödeme Günü", "necessity": "REQUIRES"},
      {"node_id": 14, "name": "Süre", "necessity": "REQUIRES"}
    ],
    "missing_recommended": [
      {"node_id": 13, "name": "Artış Oranı", "necessity": "RECOMMENDED"}
    ]
  },
  "suggestions": {
    "status": "incomplete",
    "completeness_score": 62.5,
    "suggestions": [
      {
        "type": "question",
        "field_name": "Ödeme Günü",
        "message": "Kira ödemesi ayın kaçında yapılacak?",
        "priority": 1,
        "necessity": "required"
      },
      {
        "type": "question",
        "field_name": "Süre",
        "message": "Kira sözleşmesinin süresi ne kadar?",
        "priority": 1,
        "necessity": "required"
      },
      {
        "type": "reminder",
        "field_name": "Artış Oranı",
        "message": "Yıllık kira artış oranı belirlemek faydalı olabilir.",
        "priority": 2,
        "necessity": "recommended"
      }
    ],
    "next_action": "Kullanıcıya şu soruyu sor: Kira ödemesi ayın kaçında yapılacak?",
    "llm_prompt": "## Sözleşme Analiz Raporu: Kira Sözleşmesi\n\n**Tamamlanma Oranı:** %62.5\n**Durum:** incomplete\n\n### Tespit Edilen Bilgiler:\n- ✓ Kiracı\n- ✓ Kiraya Veren\n- ✓ Kira Bedeli\n- ✓ Mülk Adresi\n- ✓ Depozito\n\n### Eksik Zorunlu Bilgiler:\n- ✗ Ödeme Günü (ZORUNLU)\n- ✗ Süre (ZORUNLU)\n\n### Eksik Önerilen Bilgiler:\n- ○ Artış Oranı (ÖNERİLEN)\n\n### Yapılacak İşlemler:\n\n**Sorulacak Sorular:**\n1. Kira ödemesi ayın kaçında yapılacak?\n2. Kira sözleşmesinin süresi ne kadar?\n\n**Hatırlatmalar:**\n- Yıllık kira artış oranı belirlemek faydalı olabilir.\n\n### Talimatlar:\nEksik zorunlu bilgileri kullanıcıdan sırayla talep et.\nHer seferinde tek bir soru sor ve cevabı bekle."
  },
  "graph_data": {
    "contract_type": "kira_sozlesmesi",
    "display_name": "Kira Sözleşmesi",
    "requires": [...],
    "recommended": [...],
    "optional": [],
    "dependencies": [],
    "field_mapping": {"7": "Kiracı", "8": "Kiraya Veren", ...}
  }
}
```

## 🗂️ Proje Yapısı

```
graphrag-server/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── contract.py      # Sözleşme şablon endpoint'leri
│   │       └── graphrag.py      # GraphRAG analiz endpoint'leri (YENİ)
│   ├── db/
│   │   └── repositories/
│   │       └── contract_repository.py
│   ├── models/
│   │   ├── request/
│   │   └── response/
│   │       ├── contract.py      # ClauseDTO, ContractTemplateResponse
│   │       └── graphrag.py      # GraphRAG response modelleri (YENİ)
│   ├── services/
│   │   ├── contract_service.py
│   │   ├── contract_generator.py # ContractGenerator sınıfı (YENİ)
│   │   └── exceptions.py
│   ├── utils/
│   │   └── db.py               # Neo4j driver singleton
│   ├── config.py
│   └── main.py
├── tests/
├── .env
├── env.example
├── pyproject.toml
├── Dockerfile
└── README.md
```

## 📊 Neo4j Graf Şeması

### Düğümler (Nodes)

- **ContractType**: `{name: string, display_name: string}`
- **Field**: `{id: int, name: string, description: string}`
- **Clause**: `{id: string, text_template: string}`

### İlişkiler (Relationships)

```
(:ContractType)-[:REQUIRES]->(:Field)      # Zorunlu alanlar
(:ContractType)-[:RECOMMENDED]->(:Field)   # Önerilen alanlar
(:ContractType)-[:OPTIONAL]->(:Field)      # İsteğe bağlı alanlar
(:Field)-[:DEPENDS_ON]->(:Field)           # Alan bağımlılıkları
(:ContractType)-[:REQUIRES]->(:Clause)     # Zorunlu maddeler
(:ContractType)-[:INCLUDES]->(:Clause)     # İsteğe bağlı maddeler
```

### Örnek Veri Kurulumu

```cypher
// Kira sözleşmesi ve alanlarını oluştur
CREATE (c:ContractType {name: 'kira_sozlesmesi', display_name: 'Kira Sözleşmesi'})

CREATE (f1:Field {id: 7, name: 'Kiracı', description: 'Kiracının tam adı'})
CREATE (f2:Field {id: 8, name: 'Kiraya Veren', description: 'Mal sahibinin adı'})
CREATE (f3:Field {id: 9, name: 'Mülk Adresi', description: 'Kiralanacak mülkün adresi'})
CREATE (f4:Field {id: 10, name: 'Kira Bedeli', description: 'Aylık kira tutarı'})
CREATE (f5:Field {id: 11, name: 'Ödeme Günü', description: 'Ödeme yapılacak gün'})
CREATE (f6:Field {id: 12, name: 'Depozito', description: 'Depozito tutarı'})
CREATE (f7:Field {id: 13, name: 'Artış Oranı', description: 'Yıllık kira artış oranı'})
CREATE (f8:Field {id: 14, name: 'Süre', description: 'Sözleşme süresi'})

// Zorunlu ilişkiler
MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 7})
CREATE (c)-[:REQUIRES]->(f)

MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 8})
CREATE (c)-[:REQUIRES]->(f)

MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 9})
CREATE (c)-[:REQUIRES]->(f)

MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 10})
CREATE (c)-[:REQUIRES]->(f)

MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 11})
CREATE (c)-[:REQUIRES]->(f)

MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 14})
CREATE (c)-[:REQUIRES]->(f)

// Önerilen ilişkiler
MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 12})
CREATE (c)-[:RECOMMENDED]->(f)

MATCH (c:ContractType {name: 'kira_sozlesmesi'}), (f:Field {id: 13})
CREATE (c)-[:RECOMMENDED]->(f)

// Bağımlılık: Kira Bedeli → Ödeme Günü
MATCH (f1:Field {id: 10}), (f2:Field {id: 11})
CREATE (f1)-[:DEPENDS_ON]->(f2)
```

## 🔄 Sistem Akışı

```
                         ┌─────────────────────────────────────────┐
                         │           KULLANICI GİRİŞİ              │
                         │  "Ahmet Yılmaz ile Mehmet Demir         │
                         │   arasında 5000 TL'lik kira sözleşmesi" │
                         └────────────────────┬────────────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              NLP-SERVER                                       │
│                         (Ayrı modül - spaCy)                                 │
│                                                                              │
│  extracted_entities = {                                                      │
│    "PERSON": ["Ahmet Yılmaz", "Mehmet Demir"],                              │
│    "MONEY": ["5000 TL"]                                                      │
│  }                                                                           │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           GRAPHRAG-SERVER                                     │
│                            (Bu Modül)                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. fetch_contract_requirements("kira_sozlesmesi")                          │
│     └── Neo4j'den: REQUIRES, RECOMMENDED, OPTIONAL, DEPENDS_ON              │
│                                                                              │
│  2. agentic_reasoning_engine(extracted_entities, graph_data)                │
│     └── Entity → Alan eşleştirmesi                                          │
│     └── Eksik alan tespiti                                                  │
│     └── Tamamlanma skoru hesaplama                                          │
│                                                                              │
│  3. generate_proactive_suggestions()                                        │
│     └── Eksik zorunlu alanlar için SORU üret                                │
│     └── Eksik önerilen alanlar için HATIRLATMA üret                         │
│     └── LLM-ready prompt oluştur                                            │
│                                                                              │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              LLM (Claude/GPT)                                 │
│                                                                              │
│  Alınan JSON ile:                                                            │
│  - Tespit edilen bilgileri doğrular                                         │
│  - Eksik bilgiler için kullanıcıya soru sorar                               │
│  - Sözleşme taslağını hazırlar                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 🧪 Test

```bash
# Dev bağımlılıklarını yükle
pip install -e ".[dev]"

# Testleri çalıştır
pytest

# Belirli testi çalıştır
pytest tests/test_contract_api.py -v
```

## 📚 API Dokümantasyonu

Sunucu çalışırken:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## 🔧 Bağımlılıklar

```toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "neo4j>=5.15.0",
    "python-dotenv>=1.0.0",
    "spacy>=3.7.0",
]
```

## 📝 Lisans

MIT License
