"""FAISS vector store — singleton via lru_cache."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from langchain_community.vectorstores import FAISS

from app.config import settings
from app.core.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

_INDEX_PATH: Path = settings.VECTOR_STORE_DIR / "faiss_index"


@lru_cache(maxsize=1)
def get_vector_store() -> FAISS:
    """Load or create a FAISS vector store."""
    embeddings = get_embedding_model()

    if (_INDEX_PATH / "index.faiss").exists():
        logger.info("Loading existing FAISS index from %s", _INDEX_PATH)
        store = FAISS.load_local(
            str(_INDEX_PATH), embeddings, allow_dangerous_deserialization=True
        )
    else:
        logger.info("Creating new (empty) FAISS index.")
        # Bootstrap with a dummy doc so the index file exists
        store = FAISS.from_texts(["__init__"], embeddings)
        store.save_local(str(_INDEX_PATH))

    return store


def persist_vector_store(store: FAISS) -> None:
    """Save the vector store to disk."""
    store.save_local(str(_INDEX_PATH))
    logger.info("Vector store persisted to %s", _INDEX_PATH)
