# RAG System — Production-Grade Retrieval-Augmented Generation

A standalone, production-grade RAG (Retrieval-Augmented Generation) system with multi-agent reasoning, adversarial stress testing, human validation, and a full evaluation pipeline.

This is an **independent project** built to serve as a robust, end-to-end intelligent document retrieval and generation platform. It is not designed as a plug-in for other projects — it is its own complete system.

---

## What This System Does

1. Ingest diverse data sources (documents, code, spreadsheets, images)
2. Parse, chunk, and enrich with metadata
3. Store in a hybrid database layer (vector + relational)
4. Route queries through a multi-agent system
5. Reason over retrieved context using a planning engine
6. Generate grounded, auditable answers via LLM
7. Evaluate quality and performance continuously
8. Stress-test against adversarial prompts
9. Gate outputs through human validation roles

---

## System Architecture

> **Tip:** You can edit and interact with this diagram using [Mermaid Live Editor](https://mermaid.live/). Copy the code below and paste it there for a full-screen, interactive experience.

```mermaid
flowchart LR
    subgraph Input["Data Sources"]
        DS1[Documents]
        DS2[Code]
        DS3[Spreadsheets]
        DS4[Images]
    end
    subgraph Processing["Data Processing"]
        DP1[Document Parser]
        DP2[Structure Analyzer]
        DP3[Chunker]
        DP4[Metadata Creator]
    end
    subgraph Storage["Database Layer"]
        VS[Vector Store\n(Qdrant/Weaviate)]
        RD[Relational DB\n(PostgreSQL)]
    end
    subgraph Agents["Multi-Agent System"]
        AG1[Agent 1]
        AG2[Agent 2]
        AG3[Agent N]
    end
    subgraph Reasoning["Reasoning Engine"]
        PL[Planner]
        TE[Tool Executor]
        CR[Conditional Router]
    end
    subgraph Eval["Evaluation"]
        LJ[LLM Judges]
        PR[Precision/Recall]
        LC[Latency/Cost]
    end
    subgraph Stress["Stress Testing"]
        PO[Prompt Injection]
        BO[Biased Opinion]
        IE[Information Evasion]
    end
    subgraph Human["Human Validation"]
        GK[Gatekeeper]
        AU[Auditor]
        STG[Strategist]
    end

    DS1 --> DP1
    DS2 --> DP1
    DS3 --> DP1
    DS4 --> DP1
    DP1 --> DP2
    DP2 --> DP3
    DP3 --> DP4
    DP4 --> VS
    DP4 --> RD
    VS --> AG1
    VS --> AG2
    VS --> AG3
    RD --> AG1
    RD --> AG2
    RD --> AG3
    AG1 --> PL
    AG2 --> PL
    AG3 --> PL
    PL --> TE
    TE --> CR
    CR --> LJ
    LJ --> PR
    PR --> LC
    LC --> PO
    PO --> BO
    BO --> IE
    IE --> GK
    GK --> AU
    AU --> STG
    STG -.-> PL
```

---

### Layer Breakdown

| Layer | Components | Responsibility |
|---|---|---|
| **Data Sources** | Documents, Code, Spreadsheets, Images | Raw input ingestion |
| **Data Processing** | Parser, Structure Analyzer, Chunker, Metadata Creator | Transform raw data into structured, retrievable units |
| **Database Layer** | Vector Store (FAISS/Chroma), Relational DB | Persist embeddings and structured metadata |
| **Multi-Agent System** | Specialized task agents | Parallel or sequential task execution |
| **Reasoning Engine** | Planner, Tool Executor, Router | Decide how to answer — decompose, retrieve, act |
| **Evaluation** | LLM-as-Judge, Precision/Recall, Latency/Cost metrics | Measure answer quality and system performance |
| **Stress Testing** | Prompt Injection, Biased Opinion, Information Evasion | Adversarial robustness testing |
| **Human Validation** | Gatekeeper, Auditor, Strategist | Human-in-the-loop review and approval |

---

## Core API

```
POST /ingest    → Parse, chunk, embed, and store documents
POST /query     → Retrieve context and generate grounded responses
GET  /health    → System health check
```

---

## Tech Stack

| Category | Technology |
|---|---|
| **Backend**        | FastAPI |
| **Vector DB**      | Qdrant / Weaviate |
| **Relational DB**  | PostgreSQL |
| **Embeddings**     | BGE-large |
| **Reranker**       | Cross-Encoder |
| **LLM**            | API (initially), self-hosted later |
| **Workers**        | Celery + Redis |
| **Monitoring**     | Prometheus + Grafana |
| **Deployment**     | Docker + Kubernetes |

---

## Setup

```bash
# Clone the repo
git clone https://github.com/satyms/RAG-system.git
cd RAG-system

# Create and activate virtual environment
python -m venv rag
.\rag\Scripts\Activate.ps1   # Windows
# source rag/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

---

## Project Structure

```
RAG-system/
│
├── app/
│   ├── api/
│   │   └── routes/          # FastAPI route handlers (ingest, query, health)
│   ├── core/
│   │   ├── ingestion.py     # Document parsing, chunking, metadata
│   │   ├── embeddings.py    # BGE-large embedding model
│   │   ├── vector_store.py  # Qdrant/Weaviate operations
│   │   ├── retrieval.py     # Semantic search & context retrieval
│   │   ├── reranker.py      # Cross-Encoder reranking
│   │   └── generation.py    # LLM generation with reasoning
│   ├── models/
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── workers/
│   │   └── celery_worker.py # Celery background tasks
│   ├── utils/
│   │   └── helpers.py       # Shared utilities
│   ├── config.py            # System configuration
│   └── main.py              # FastAPI app entrypoint
│
├── monitoring/
│   ├── prometheus.yml       # Prometheus config
│   └── grafana/             # Grafana dashboards
├── deployments/
│   ├── docker-compose.yml   # Local dev
│   └── k8s/                 # Kubernetes manifests
├── static/                  # Frontend UI
├── uploads/                 # Uploaded documents
├── vector_store_data/       # Persisted vector store
└── requirements.txt
```

---

## Data & Query Flow

**Ingestion:**
```
Raw Document → Parse → Chunk → Embed → Store (Vector DB + Metadata DB)
```

**Query:**
```
User Query → Embed → Vector Search → Retrieve Top-K Chunks
    → Multi-Agent Routing → Reasoning Engine → LLM Generation
    → Evaluation → (Stress Test / Human Gate) → Final Response
```

---

## Key Design Principles

* **Modular** — every layer is independently replaceable
* **Multi-agent** — specialized agents for different reasoning tasks
* **Adversarial-aware** — built-in stress testing against prompt injection, bias, and evasion
* **Human-in-the-loop** — gatekeeper / auditor / strategist validation layer
* **Observable** — LLM-as-Judge evaluation with precision, recall, latency, and cost metrics
* **Offline-capable** — runs fully local with open-source models

---

## Example Use Cases

* Enterprise Document Intelligence
* Legal Contract Analysis
* Medical Knowledge Assistant
* Codebase Q&A
* Research Paper Summarization
* Compliance & Audit Automation

---

## Roadmap

- [ ] Qdrant/Weaviate integration
- [ ] PostgreSQL production support
- [ ] BGE-large embedding pipeline
- [ ] Cross-Encoder reranking
- [ ] Celery + Redis background workers
- [ ] Prometheus + Grafana monitoring
- [ ] Docker & Kubernetes deployment
- [ ] Streaming responses
- [ ] Multi-tenant document namespaces
- [ ] Self-hosted LLM support
- [ ] Automated red-teaming pipeline
- [ ] Dashboard UI for evaluation metrics
- [ ] Full LangGraph multi-agent orchestration
- [ ] CI/CD with automated RAGAS evaluation on PRs