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

```mermaid
flowchart TD
    DS["Data Sources\nDocuments · Code · Spreadsheets · Images"]
    DP["Data Processing\nDocument Parsing · Structure Analysis\nChunking · Metadata Creation"]
    DB["Database Layer\nVector Store · Relational Database"]
    MAS["Multi-Agent System\nAgent 1 · Agent 2 · Agent N"]
    RE["Reasoning Engine\nPlanning · Tool Execution · Routing"]
    EVAL["Evaluation\nLLM Judges · Precision/Recall · Latency · Cost"]
    ST["Stress Testing\nPrompt Injection · Biased Opinion · Information Evasion"]
    HV["Human Validation\nGatekeeper · Auditor · Strategist"]

    DS --> DP
    DP --> DB
    DB --> MAS
    MAS --> RE
    RE --> EVAL
    EVAL --> ST
    ST --> HV
    HV -->|Feedback Loop| RE
```

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
| **Backend** | Python 3.10+, FastAPI |
| **Orchestration** | LangChain, LangGraph |
| **Embeddings** | SentenceTransformers (BGE / MiniLM) |
| **Vector Store** | FAISS / ChromaDB |
| **Relational DB** | SQLite / PostgreSQL |
| **LLM** | Ollama (`llama3.2`) by default, OpenAI-compatible APIs, optional Gemini |
| **Evaluation** | LLM-as-Judge, RAGAS metrics |
| **Multi-Agent** | LangGraph agent graphs |

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

# Pull the default Ollama model
ollama pull llama3.2

# Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

By default, the app uses Ollama at `http://localhost:11434` with the `llama3.2` model.

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
│   │   ├── embeddings.py    # Embedding model interface
│   │   ├── vector_store.py  # Vector DB operations
│   │   ├── retrieval.py     # Semantic search & context retrieval
│   │   └── generation.py   # LLM generation with reasoning
│   ├── models/
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── utils/
│   │   └── helpers.py       # Shared utilities
│   ├── config.py            # System configuration
│   └── main.py              # FastAPI app entrypoint
│
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

- [ ] Hybrid search (BM25 + dense vector)
- [ ] Cross-encoder reranking
- [ ] Streaming responses
- [ ] Multi-tenant document namespaces
- [ ] Graph RAG (knowledge graph integration)
- [ ] Automated red-teaming pipeline
- [ ] Dashboard UI for evaluation metrics
- [ ] Full LangGraph multi-agent orchestration
- [ ] CI/CD with automated RAGAS evaluation on PRs