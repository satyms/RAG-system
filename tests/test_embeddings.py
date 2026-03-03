"""Unit tests for the embedding module (app.core.embeddings)."""

from __future__ import annotations

import pytest

from app.core.embeddings import _clean_text, clean_texts, embed_text, embed_batch
from app.config import settings


# ── _clean_text ──────────────────────────────────────────────

class TestCleanText:
    def test_strips_whitespace(self):
        assert _clean_text("  hello  ") == "hello"

    def test_collapses_internal_spaces(self):
        assert _clean_text("hello   world") == "hello world"

    def test_collapses_newlines_and_tabs(self):
        assert _clean_text("hello\n\nworld\there") == "hello world here"

    def test_unicode_normalization(self):
        # NFKC normalizes ﬁ ligature → 'fi'
        assert "fi" in _clean_text("\ufb01nd")

    def test_empty_string(self):
        assert _clean_text("") == ""
        assert _clean_text("   ") == ""


# ── clean_texts ──────────────────────────────────────────────

class TestCleanTexts:
    def test_filters_empties(self):
        result = clean_texts(["hello", "", "   ", "world"])
        assert result == ["hello", "world"]

    def test_cleans_each(self):
        result = clean_texts(["  one  ", "two\nthree"])
        assert result == ["one", "two three"]

    def test_empty_input(self):
        assert clean_texts([]) == []


# ── embed_text ───────────────────────────────────────────────

class TestEmbedText:
    def test_returns_correct_dimension(self):
        vec = embed_text("This is a test sentence.")
        assert isinstance(vec, list)
        assert len(vec) == settings.EMBEDDING_DIMENSION

    def test_values_are_floats(self):
        vec = embed_text("Test embedding")
        assert all(isinstance(v, float) for v in vec)

    def test_normalized_vector(self):
        """BGE embeddings with normalize=True should have unit norm."""
        vec = embed_text("Normalized check")
        norm = sum(v ** 2 for v in vec) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="empty"):
            embed_text("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            embed_text("   ")


# ── embed_batch ──────────────────────────────────────────────

class TestEmbedBatch:
    def test_returns_correct_count(self):
        vecs = embed_batch(["first", "second", "third"])
        assert len(vecs) == 3

    def test_each_vector_correct_dim(self):
        vecs = embed_batch(["alpha", "beta"])
        for v in vecs:
            assert len(v) == settings.EMBEDDING_DIMENSION

    def test_different_texts_different_embeddings(self):
        vecs = embed_batch(["cats are great", "quantum physics equations"])
        # Cosine similarity should be < 1 for semantically different texts
        dot = sum(a * b for a, b in zip(vecs[0], vecs[1]))
        assert dot < 0.99

    def test_empty_after_cleaning_raises(self):
        with pytest.raises(ValueError, match="No valid"):
            embed_batch(["", "   "])
