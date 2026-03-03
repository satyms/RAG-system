"""SQLAlchemy ORM models — Documents, Chunks, QueryLogs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """Uploaded document record."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(512), nullable=False)
    file_hash = Column(String(128), nullable=True)
    upload_timestamp = Column(DateTime(timezone=True), default=_utcnow)
    status = Column(String(32), default="uploaded")  # uploaded | processing | indexed | failed

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Individual text chunk belonging to a document."""

    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)  # page_number, section, source
    embedding_id = Column(String(256), nullable=True)  # Qdrant point ID

    document = relationship("Document", back_populates="chunks")


class QueryLog(Base):
    """Log of every user query for observability."""

    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = Column(Text, nullable=False)
    retrieved_chunks = Column(JSON, default=list)  # list of chunk IDs + scores
    response = Column(Text, nullable=True)
    similarity_scores = Column(JSON, default=list)
    latency_ms = Column(Float, nullable=True)
    token_usage = Column(JSON, default=dict)  # prompt_tokens, completion_tokens
    confidence_score = Column(Float, nullable=True)  # avg similarity
    timestamp = Column(DateTime(timezone=True), default=_utcnow)
