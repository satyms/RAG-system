"""Orchestrator — routes queries through the multi-agent pipeline with conditional logic."""

from __future__ import annotations

import logging
import time

from app.agents.base import AgentContext, AgentRegistry
from app.agents.planner import PlannerAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.tool_agent import ToolAgent
from app.agents.synthesis import SynthesisAgent
from app.core.prompt_guard import check_prompt_injection, sanitize_query, filter_context_injections

logger = logging.getLogger(__name__)

# ── Register all agents on import ────────────────────────────
_planner = PlannerAgent()
_retrieval = RetrievalAgent()
_tool = ToolAgent()
_synthesis = SynthesisAgent()

AgentRegistry.register(_planner)
AgentRegistry.register(_retrieval)
AgentRegistry.register(_tool)
AgentRegistry.register(_synthesis)


def orchestrate(
    query: str,
    top_k: int | None = None,
    source_filter: str | None = None,
    hybrid_weight: float | None = None,
    debug: bool = False,
) -> dict:
    """
    Run the full multi-agent pipeline:

    1. Security check (prompt injection)
    2. Planner → classify intent, decompose
    3. Conditional routing:
       - simple → retrieval → synthesis
       - complex/multi_step → retrieval per sub-task → synthesis
       - tool_required → tool agent → retrieval → synthesis
    4. Faithfulness evaluation
    5. Return structured response

    Returns a dict matching QueryResponse fields plus agent debug info.
    """
    total_start = time.perf_counter()

    # ── 0. Sanitize & security ───────────────────────────────
    clean_query = sanitize_query(query)
    injection = check_prompt_injection(clean_query)
    if injection.blocked:
        return {
            "answer": "",
            "blocked": True,
            "block_reason": "Prompt injection detected",
            "risk_score": injection.risk_score,
        }

    # ── Build context ────────────────────────────────────────
    ctx = AgentContext(
        query=clean_query,
        original_query=query,
    )
    if source_filter:
        ctx.metadata["source_filter"] = source_filter
    if top_k:
        ctx.metadata["requested_top_k"] = top_k
    if hybrid_weight is not None:
        ctx.metadata["hybrid_weight_override"] = hybrid_weight

    # ── 1. Planning ──────────────────────────────────────────
    ctx = _planner.execute(ctx)

    # ── 2. Conditional routing ───────────────────────────────
    agents_needed = ctx.metadata.get("agents_needed", ["retrieval", "synthesis"])

    # Tool agent (if needed)
    if "tool" in agents_needed:
        ctx = _tool.execute(ctx)

    # Retrieval
    if "retrieval" in agents_needed:
        # Apply hybrid weight override
        if hybrid_weight is not None:
            from app.config import settings
            _orig_weight = settings.HYBRID_WEIGHT
            settings.HYBRID_WEIGHT = hybrid_weight

        ctx = _retrieval.execute(ctx)

        # Filter context injections
        ctx.retrieved_chunks = filter_context_injections(ctx.retrieved_chunks)

        if hybrid_weight is not None:
            settings.HYBRID_WEIGHT = _orig_weight  # noqa: F821

    # Multi-step: run synthesis per sub-task, then final synthesis
    if ctx.query_type == "multi_step" and len(ctx.sub_tasks) > 1:
        for i, task in enumerate(ctx.sub_tasks):
            # Create a mini-context for each sub-task
            sub_ctx = AgentContext(
                query=task,
                original_query=ctx.original_query,
                intent=ctx.intent,
                complexity="low",  # Each sub-task treated as simple
                query_type="simple",
                sub_tasks=[task],
                retrieved_chunks=ctx.retrieved_chunks,
                context_text=ctx.context_text,
                tool_results=ctx.tool_results,
            )
            sub_ctx = _synthesis.execute(sub_ctx)
            ctx.intermediate_answers.append(sub_ctx.final_answer)
            ctx.add_step("orchestrator", f"sub_answer_{i+1}", sub_ctx.final_answer[:100])

    # Final synthesis
    ctx = _synthesis.execute(ctx)

    # ── 3. Faithfulness evaluation ───────────────────────────
    faithfulness_score = None
    is_grounded = "unknown"
    try:
        from app.core.faithfulness import evaluate_faithfulness
        faith = evaluate_faithfulness(
            question=clean_query,
            answer=ctx.final_answer,
            context_chunks=ctx.retrieved_chunks,
        )
        faithfulness_score = faith.get("faithfulness_score")
        is_grounded = faith.get("is_grounded", "unknown")
    except Exception:
        logger.debug("Faithfulness evaluation skipped", exc_info=True)

    total_ms = round((time.perf_counter() - total_start) * 1000, 1)
    ctx.latency["total_ms"] = total_ms

    # ── 4. Build response ────────────────────────────────────
    from app.config import settings
    low_confidence = ctx.confidence < settings.CONFIDENCE_THRESHOLD if ctx.confidence else False

    response = {
        "answer": ctx.final_answer,
        "sources": [
            {
                "content": c.get("content", ""),
                "source": c.get("source", ""),
                "score": c.get("score"),
                "chunk_index": c.get("chunk_index"),
                "page_number": c.get("page_number"),
                "reranker_score": c.get("reranker_score"),
                "hybrid_score": c.get("hybrid_score"),
            }
            for c in ctx.retrieved_chunks
        ],
        "confidence_score": ctx.confidence,
        "latency_ms": total_ms,
        "token_usage": ctx.metadata.get("token_usage", {}),
        "retrieval_metadata": ctx.metadata.get("retrieval", {}),
        "faithfulness_score": faithfulness_score,
        "is_grounded": is_grounded,
        "low_confidence": low_confidence,
        # Phase 4 extras
        "agent_metadata": {
            "query_type": ctx.query_type,
            "intent": ctx.intent,
            "complexity": ctx.complexity,
            "sub_tasks": ctx.sub_tasks,
            "agents_used": ctx.metadata.get("agents_needed", []),
            "latency_breakdown": ctx.latency,
            "requires_human_review": ctx.requires_human_review,
            "human_review_reason": ctx.human_review_reason,
        },
        "citations": ctx.citations,
        "blocked": False,
    }

    if debug:
        response["debug"] = {
            "reasoning_steps": ctx.reasoning_steps,
            "messages": [
                {"role": m.role.value, "content": m.content, "id": m.message_id}
                for m in ctx.messages
            ],
            "errors": ctx.errors,
            "debug_info": ctx.debug_info,
        }

    return response
