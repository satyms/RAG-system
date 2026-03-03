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
    LLM_PROVIDER: str = "google_genai"

    # Google Generative AI (Gemini)
    GOOGLE_API_KEY: str = ""
    GOOGLE_MODEL: str = "gemini-2.0-flash"

    # --- PostgreSQL ---
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag_password@localhost:5432/rag_db"

    # --- Qdrant ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "rag_chunks"

    # --- Security ---
    MAX_FILE_SIZE_MB: int = 50
    RATE_LIMIT: str = "30/minute"

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

