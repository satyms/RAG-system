"""Application configuration and settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # --- App ---
    APP_NAME: str = "RAG System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    VECTOR_STORE_DIR: Path = BASE_DIR / "vector_store_data"

    # --- Embedding Model ---
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIMENSION: int = 768

    # --- Chunking ---
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 120

    # --- Retrieval ---
    TOP_K: int = 5

    # --- LLM / Generation ---
    LLM_PROVIDER: str = "ollama"  # "ollama" | "openai" | "google_genai"
    # --- Hybrid Retrieval (Phase 2) ---
    TOP_K_DENSE: int = 20
    TOP_K_BM25: int = 20
    HYBRID_WEIGHT: float = 0.7          # 0 = pure BM25, 1 = pure dense
    SCORE_THRESHOLD: float = 0.0        # discard chunks below this score
    CONFIDENCE_THRESHOLD: float = 0.3   # flag low-confidence queries

    # --- Reranker (Phase 2) ---
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_TOP_K: int = 5             # final chunks after reranking
    RERANKER_ENABLED: bool = True

    # --- LLM / Generation (Ollama) ---
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # --- PostgreSQL ---
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag_password@localhost:5432/rag_db"

    # --- Qdrant ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "rag_chunks"

    # --- Security ---
    MAX_FILE_SIZE_MB: int = 50
    RATE_LIMIT: str = "30/minute"

    # --- Phase 3: Security ---
    API_KEY: str = ""                           # Static API key (empty = no auth)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # --- Phase 3: Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 3600               # 1 hour default
    CACHE_ENABLED: bool = True

    # --- Phase 3: Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- Phase 3: Rate Limiting ---
    RATE_LIMIT_QUERY: str = "30/minute"
    RATE_LIMIT_INGEST: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

