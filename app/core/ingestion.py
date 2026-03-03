"""Document ingestion — parse, chunk, embed, store in Qdrant + Postgres."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredFileLoader,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embeddings import embed_batch, clean_texts
from app.core.vector_store import upsert_embeddings, delete_document_vectors
from app.db.models import Document, Chunk

logger = logging.getLogger(__name__)

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)

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


def _extract_page_number(doc) -> int | None:
    """Try to get page number from LangChain document metadata."""
    return doc.metadata.get("page")


def _extract_section(text: str) -> str | None:
    """Try to extract heading / section from first line of chunk."""
    first_line = text.strip().split("\n")[0]
    # Simple heuristic: if line is short and title-case-ish, it might be a heading
    if len(first_line) < 120 and re.match(r"^[A-Z#]", first_line):
        return first_line.strip("#").strip()
    return None


async def ingest_file(file_path: Path, db: AsyncSession) -> tuple[int, str]:
    """
    Full ingestion pipeline for a single file:
      1. Parse document
      2. Chunk with metadata
      3. Embed (batch)
      4. Store in Qdrant
      5. Store metadata in Postgres

    Returns (num_chunks, document_id).
    """
    filename = file_path.name
    logger.info("Starting ingestion: %s", filename)

    # ── 1. Create DB record ──────────────────────────────────
    from app.utils.helpers import file_hash

    doc_record = Document(
        filename=filename,
        file_hash=file_hash(file_path),
        status="processing",
    )
    db.add(doc_record)
    await db.flush()  # get the ID
    doc_id = str(doc_record.id)

    try:
        # ── 2. Parse ─────────────────────────────────────────
        loader = _get_loader(file_path)
        documents = loader.load()

        if not documents:
            doc_record.status = "failed"
            await db.commit()
            raise ValueError(f"No content extracted from {filename}")

        for doc in documents:
            doc.metadata.setdefault("source", filename)

        # ── 3. Chunk ─────────────────────────────────────────
        chunks = _SPLITTER.split_documents(documents)
        logger.info("Split %s into %d chunks", filename, len(chunks))

        if not chunks:
            doc_record.status = "failed"
            await db.commit()
            raise ValueError(f"No chunks generated from {filename}")

        # ── 4. Embed ─────────────────────────────────────────
        texts = [c.page_content for c in chunks]
        cleaned = clean_texts(texts)
        vectors = embed_batch(cleaned)

        # ── 5. Build payloads & upsert to Qdrant ────────────
        payloads = []
        for i, (chunk, text) in enumerate(zip(chunks, cleaned)):
            payloads.append({
                "content": text,
                "source": filename,
                "document_id": doc_id,
                "chunk_index": i,
                "page_number": _extract_page_number(chunk) or 0,
                "section": _extract_section(text),
            })

        point_ids = upsert_embeddings(vectors, payloads)

        # ── 6. Store chunks in Postgres ──────────────────────
        for i, (text, pid) in enumerate(zip(cleaned, point_ids)):
            chunk_record = Chunk(
                document_id=doc_record.id,
                chunk_index=i,
                content=text,
                metadata_={
                    "source": filename,
                    "page_number": payloads[i].get("page_number"),
                    "section": payloads[i].get("section"),
                },
                embedding_id=pid,
            )
            db.add(chunk_record)

        doc_record.status = "indexed"
        await db.commit()

        logger.info("Ingestion complete: %s — %d chunks", filename, len(chunks))
        return len(chunks), doc_id

    except Exception:
        doc_record.status = "failed"
        await db.commit()
        # Clean up any partial Qdrant data
        try:
            delete_document_vectors(filename)
        except Exception:
            pass
        raise

