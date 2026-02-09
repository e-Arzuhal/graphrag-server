# e-Arzuhal GraphRAG Server

A Retrieval-Augmented Generation (RAG) server for legal document generation using a Neo4j Knowledge Graph.

## 🚀 Features

- Query contract templates from a Neo4j knowledge graph
- Retrieve mandatory and optional clauses for contract types
- RESTful API with FastAPI
- Repository pattern for clean architecture
- Comprehensive API documentation with Swagger/OpenAPI

## 📦 Installation

### Prerequisites

- Python 3.10+
- Neo4j 5.x (running locally or in Docker)

### Setup

1. Clone the repository and install dependencies:

```bash
cd graphrag-server
pip install -e .
```

2. Configure environment variables:

```bash
cp env.example .env
# Edit .env with your Neo4j credentials
```

3. Start the server:

```bash
uvicorn app.main:app --reload
```

### Docker

```bash
# Build the image
docker build -t graphrag-server .

# Run with environment variables
docker run -p 8000:8000 \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=your_password \
  graphrag-server
```

## 📖 API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Detailed health status |
| GET | `/api/v1/template/` | List all contract types |
| GET | `/api/v1/template/{contract_type}` | Get contract template |

### Example Request

```bash
curl http://localhost:8000/api/v1/template/borc_sozlesmesi
```

### Example Response

```json
{
  "contract_type": "borc_sozlesmesi",
  "display_name": "Borç Sözleşmesi",
  "clauses": [
    {
      "id": "clause_001",
      "template": "İşbu sözleşme {{taraf1}} ile {{taraf2}} arasında...",
      "necessity": "mandatory"
    },
    {
      "id": "clause_002",
      "template": "Teminat olarak {{teminat}} sunulabilir.",
      "necessity": "optional"
    }
  ]
}
```

## 🗂️ Project Structure

```
graphrag-server/
├── app/
│   ├── api/
│   │   └── routes/          # FastAPI routers
│   │       └── contract.py  # Contract template endpoints
│   ├── db/
│   │   └── repositories/    # Neo4j database queries
│   │       └── contract_repository.py
│   ├── models/
│   │   ├── request/         # Input validation models
│   │   └── response/        # Output models
│   │       └── contract.py  # ClauseDTO, ContractTemplateResponse
│   ├── services/            # Business logic
│   │   └── contract_service.py
│   ├── utils/               # Utilities
│   │   └── db.py           # Neo4j driver singleton
│   ├── config.py           # Application settings
│   └── main.py             # FastAPI app entry point
├── tests/                   # Test suite
├── .env                     # Environment variables (not in git)
├── env.example             # Example environment file
├── pyproject.toml          # Python project configuration
├── Dockerfile              # Container configuration
└── README.md
```

## 📊 Neo4j Graph Schema

The knowledge graph uses the following schema:

### Nodes

- **ContractType**: `{name: string, display_name: string}`
- **Clause**: `{id: string, text_template: string}`

### Relationships

- `(:ContractType)-[:REQUIRES {type: "mandatory"}]->(:Clause)`
- `(:ContractType)-[:INCLUDES {type: "optional"}]->(:Clause)`

### Sample Data Setup

```cypher
// Create contract type
CREATE (c:ContractType {name: 'borc_sozlesmesi', display_name: 'Borç Sözleşmesi'})

// Create clauses
CREATE (cl1:Clause {id: 'clause_001', text_template: 'İşbu sözleşme {{taraf1}} ile {{taraf2}} arasında akdedilmiştir.'})
CREATE (cl2:Clause {id: 'clause_002', text_template: 'Borç miktarı {{miktar}} TL olarak belirlenmiştir.'})
CREATE (cl3:Clause {id: 'clause_003', text_template: 'Teminat olarak {{teminat}} sunulabilir.'})

// Create relationships
MATCH (c:ContractType {name: 'borc_sozlesmesi'}), (cl:Clause {id: 'clause_001'})
CREATE (c)-[:REQUIRES {type: 'mandatory'}]->(cl)

MATCH (c:ContractType {name: 'borc_sozlesmesi'}), (cl:Clause {id: 'clause_002'})
CREATE (c)-[:REQUIRES {type: 'mandatory'}]->(cl)

MATCH (c:ContractType {name: 'borc_sozlesmesi'}), (cl:Clause {id: 'clause_003'})
CREATE (c)-[:INCLUDES {type: 'optional'}]->(cl)
```

## 🧪 Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## 📝 License

MIT License
