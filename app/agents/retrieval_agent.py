"""Retrieval Agent — performs hybrid search, reranking, and context dedup."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict

from app.agents.base import BaseAgent, AgentContext, AgentMessage, MessageRole
from app.config import settings
from app.core.retrieval import retrieve_chunks

logger = logging.getLogger(__name__)


def _deduplicate_chunks(chunks: list[dict], similarity_threshold: float = 0.95) -> list[dict]:
    """Remove near-duplicate chunks by content overlap."""
    seen: OrderedDict[str, dict] = OrderedDict()
    for chunk in chunks:
        content = chunk.get("content", "").strip()
        # Simple dedup: skip if >95% of content already seen
        is_dup = False
        for existing_content in seen:
            if len(content) > 20 and len(existing_content) > 20:
                # Jaccard-ish check on word sets
                words_new = set(content.lower().split())
                words_old = set(existing_content.lower().split())
                if words_old and words_new:
                    overlap = len(words_new & words_old) / max(len(words_new | words_old), 1)
                    if overlap > similarity_threshold:
                        is_dup = True
                        break
        if not is_dup:
            seen[content] = chunk
    return list(seen.values())


def _prioritize_chunks(chunks: list[dict], token_budget: int = 4000) -> list[dict]:
    """Select chunks that fit within the token budget, prioritising by score."""
    # Rough token estimate: 1 token ≈ 4 chars
    budget_chars = token_budget * 4
    selected = []
    total_chars = 0

    for chunk in chunks:
        content = chunk.get("content", "")
        if total_chars + len(content) > budget_chars:
            break
        selected.append(chunk)
        total_chars += len(content)

    return selected


class RetrievalAgent(BaseAgent):
    """Performs hybrid search, deduplication, and context selection."""

    name = "retrieval"
    description = "Queries vector database with hybrid search and reranking"

    def execute(self, ctx: AgentContext) -> AgentContext:
        t0 = time.perf_counter()

        self._log(ctx, "start_retrieval", f"sub_tasks={len(ctx.sub_tasks)}")

        all_chunks: list[dict] = []
        all_metadata: list[dict] = []

        # Dynamically adjust top_k based on complexity
        base_k = settings.TOP_K
        if ctx.complexity == "high":
            top_k = min(base_k * 2, 20)
        elif ctx.complexity == "medium":
            top_k = min(base_k + 3, 15)
        else:
            top_k = base_k

        ctx.metadata["dynamic_top_k"] = top_k
        self._log(ctx, "dynamic_top_k", f"k={top_k} (complexity={ctx.complexity})")

        # Retrieve for each sub-task
        for i, task in enumerate(ctx.sub_tasks):
            self._log(ctx, "retrieve_subtask", f"[{i+1}/{len(ctx.sub_tasks)}] {task[:60]}")
            try:
                result = retrieve_chunks(
                    task,
                    top_k=top_k,
                    source_filter=ctx.metadata.get("source_filter"),
                )
                chunks = result["chunks"]
                meta = result["metadata"]
                all_chunks.extend(chunks)
                all_metadata.append(meta)
                self._log(ctx, "subtask_results", f"{len(chunks)} chunks retrieved")
            except Exception as exc:
                ctx.errors.append(f"Retrieval failed for sub-task {i+1}: {exc}")
                logger.error("Retrieval agent error on sub-task %d: %s", i + 1, exc)

        # Deduplicate across all sub-task results
        deduped = _deduplicate_chunks(all_chunks)
        self._log(ctx, "dedup", f"{len(all_chunks)} → {len(deduped)} chunks after dedup")

        # Prioritize within token budget
        prioritized = _prioritize_chunks(deduped)
        self._log(ctx, "prioritize", f"{len(prioritized)} chunks within token budget")

        ctx.retrieved_chunks = prioritized

        # Build context text for synthesis
        context_parts = []
        for i, c in enumerate(prioritized, 1):
            source = c.get("source", "unknown")
            page = c.get("page_number", "")
            header = f"[Source {i}: {source}"
            if page:
                header += f", page {page}"
            header += "]"
            context_parts.append(f"{header}\n{c['content']}")
        ctx.context_text = "\n\n---\n\n".join(context_parts) or "No relevant context found."

        # Build citations
        ctx.citations = [
            {
                "index": i + 1,
                "source": c.get("source", "unknown"),
                "page": c.get("page_number"),
                "score": c.get("reranker_score") or c.get("hybrid_score") or c.get("score"),
                "preview": c.get("content", "")[:150],
            }
            for i, c in enumerate(prioritized)
        ]

        # Aggregate metadata
        ctx.metadata["retrieval"] = {
            "total_chunks_raw": len(all_chunks),
            "total_chunks_deduped": len(deduped),
            "total_chunks_selected": len(prioritized),
            "sub_task_metadata": all_metadata,
        }

        ctx.add_message(AgentMessage(
            role=MessageRole.RETRIEVAL,
            content={
                "chunks_count": len(prioritized),
                "sources": list({c.get("source", "") for c in prioritized}),
            },
        ))

        ctx.latency["retrieval_agent_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return ctx
