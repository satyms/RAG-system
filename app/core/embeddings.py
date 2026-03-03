"""Embedding service — BGE model with batching & input cleaning."""

from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache

import torch
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


# ── Input cleaning ───────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Strip, normalize, and remove excess whitespace."""
    text = text.strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text


def clean_texts(texts: list[str]) -> list[str]:
    """Clean a list of texts, filtering out empties."""
    return [t for raw in texts if (t := _clean_text(raw))]


# ── Model ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Return a cached SentenceTransformer model."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading embedding model: %s (device=%s)", settings.EMBEDDING_MODEL_NAME, device)
    model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME, device=device)
    logger.info("Embedding model loaded — dimension=%d", model.get_sentence_embedding_dimension())
    return model


# ── Public API ───────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a list of floats."""
    model = get_embedding_model()
    cleaned = _clean_text(text)
    if not cleaned:
        raise ValueError("Cannot embed empty text")
    vector = model.encode(cleaned, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed a batch of texts. Returns list of float lists."""
    model = get_embedding_model()
    cleaned = clean_texts(texts)
    if not cleaned:
        raise ValueError("No valid texts to embed after cleaning")
    vectors = model.encode(cleaned, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()

