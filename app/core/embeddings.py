"""Embedding model loader — singleton via lru_cache."""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """Return a cached HuggingFace embedding model."""
    logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL_NAME)
    model = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    logger.info("Embedding model loaded.")
    return model
