"""Document ingestion — load, split, and add to vector store."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredFileLoader,
)

from app.config import settings
from app.core.vector_store import get_vector_store, persist_vector_store

logger = logging.getLogger(__name__)

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    length_function=len,
)

# Map common extensions to their LangChain loader
_LOADER_MAP: dict[str, type] = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".md": TextLoader,
}


def _get_loader(file_path: Path):
    """Pick the right document loader for the file type."""
    ext = file_path.suffix.lower()
    loader_cls = _LOADER_MAP.get(ext, UnstructuredFileLoader)
    return loader_cls(str(file_path))


def ingest_file(file_path: Path) -> int:
    """
    Ingest a single file into the vector store.

    Returns the number of chunks created.
    """
    logger.info("Ingesting file: %s", file_path.name)

    loader = _get_loader(file_path)
    documents = loader.load()

    # Add source metadata
    for doc in documents:
        doc.metadata.setdefault("source", file_path.name)

    chunks = _SPLITTER.split_documents(documents)
    logger.info("Split into %d chunks.", len(chunks))

    store = get_vector_store()
    store.add_documents(chunks)
    persist_vector_store(store)

    logger.info("Ingestion complete for %s", file_path.name)
    return len(chunks)
