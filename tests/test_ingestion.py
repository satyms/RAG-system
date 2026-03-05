"""Unit tests for the document ingestion pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.core.ingestion import (
    _get_loader,
    _extract_section,
    _extract_page_number,
    ingest_file,
)


class TestGetLoader:
    def test_pdf_uses_correct_loader_class(self):
        """Verify _LOADER_MAP maps .pdf to PyPDFLoader."""
        from app.core.ingestion import _LOADER_MAP
        from langchain_community.document_loaders import PyPDFLoader
        assert _LOADER_MAP[".pdf"] is PyPDFLoader

    def test_txt_loader(self):
        loader = _get_loader(Path("notes.txt"))
        assert "Text" in type(loader).__name__

    def test_md_loader(self):
        loader = _get_loader(Path("readme.md"))
        assert "Text" in type(loader).__name__

    def test_unknown_extension_uses_unstructured(self):
        loader = _get_loader(Path("data.csv"))
        assert "Unstructured" in type(loader).__name__


class TestExtractSection:
    def test_heading_line(self):
        result = _extract_section("# Introduction\nSome content here")
        assert result == "Introduction"

    def test_uppercase_line(self):
        result = _extract_section("CHAPTER 1\nDetails follow")
        assert result == "CHAPTER 1"

    def test_long_line_returns_none(self):
        long_line = "a" * 150 + "\nrest of content"
        result = _extract_section(long_line)
        assert result is None

    def test_lowercase_start_returns_none(self):
        result = _extract_section("some lowercase text\nmore text")
        assert result is None


class TestExtractPageNumber:
    def test_with_page_metadata(self):
        doc = MagicMock()
        doc.metadata = {"page": 3}
        assert _extract_page_number(doc) == 3

    def test_without_page_metadata(self):
        doc = MagicMock()
        doc.metadata = {}
        assert _extract_page_number(doc) is None


class TestIngestFile:
    @pytest.mark.asyncio
    @patch("app.core.ingestion.delete_document_vectors")
    @patch("app.core.ingestion.upsert_embeddings")
    @patch("app.core.ingestion.embed_batch")
    @patch("app.core.ingestion.clean_texts")
    @patch("app.core.ingestion._get_loader")
    @patch("app.utils.helpers.file_hash", return_value="abc123")
    async def test_successful_ingest(
        self, mock_hash, mock_loader_fn, mock_clean, mock_embed, mock_upsert, mock_delete
    ):
        # Setup mock loader
        mock_doc = MagicMock()
        mock_doc.page_content = "This is chunk content about AI."
        mock_doc.metadata = {"source": "test.txt", "page": 1}
        mock_loader = MagicMock()
        mock_loader.load.return_value = [mock_doc]
        mock_loader_fn.return_value = mock_loader

        # Mock text processing
        mock_clean.return_value = ["This is chunk content about AI."]
        mock_embed.return_value = [[0.1] * 768]
        mock_upsert.return_value = ["point-id-1"]

        # Mock DB session
        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"This is chunk content about AI.")
            tmp_path = Path(f.name)

        with patch("app.core.ingestion._SPLITTER") as mock_splitter:
            mock_chunk = MagicMock()
            mock_chunk.page_content = "This is chunk content about AI."
            mock_chunk.metadata = {"source": "test.txt", "page": 1}
            mock_splitter.split_documents.return_value = [mock_chunk]

            num_chunks, doc_id = await ingest_file(tmp_path, db)

        assert num_chunks == 1
        assert doc_id is not None
        mock_embed.assert_called_once()
        mock_upsert.assert_called_once()
        db.commit.assert_awaited()
        tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    @patch("app.core.ingestion._get_loader")
    @patch("app.utils.helpers.file_hash", return_value="abc123")
    async def test_empty_document_raises(self, mock_hash, mock_loader_fn):
        mock_loader = MagicMock()
        mock_loader.load.return_value = []  # No content extracted
        mock_loader_fn.return_value = mock_loader

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"some content")
            tmp_path = Path(f.name)

        with pytest.raises(ValueError, match="No content"):
            await ingest_file(tmp_path, db)

        tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    @patch("app.core.ingestion.delete_document_vectors")
    @patch("app.core.ingestion._get_loader")
    @patch("app.utils.helpers.file_hash", return_value="abc123")
    async def test_no_chunks_raises(self, mock_hash, mock_loader_fn, mock_delete):
        mock_doc = MagicMock()
        mock_doc.page_content = "A"
        mock_doc.metadata = {"source": "test.txt"}
        mock_loader = MagicMock()
        mock_loader.load.return_value = [mock_doc]
        mock_loader_fn.return_value = mock_loader

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"A")
            tmp_path = Path(f.name)

        with patch("app.core.ingestion._SPLITTER") as mock_splitter:
            mock_splitter.split_documents.return_value = []  # No chunks

            with pytest.raises(ValueError, match="No chunks"):
                await ingest_file(tmp_path, db)

        tmp_path.unlink(missing_ok=True)
