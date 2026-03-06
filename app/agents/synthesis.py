"""Synthesis Agent — combines context and tool results into a final grounded answer."""

from __future__ import annotations

import logging
import time
import json
from functools import lru_cache

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from app.agents.base import BaseAgent, AgentContext, AgentMessage, MessageRole
from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt templates per intent ──────────────────────────────

_BASE_SYSTEM = (
    "You are a precise, helpful AI assistant. "
    "Answer the user's question using ONLY the provided context below. "
    "If the context does not contain enough information to answer, "
    "clearly state that the information is not available in the provided documents.\n\n"
    "Rules:\n"
    "- Be concise and factual.\n"
    "- Cite sources using [Source N] notation.\n"
    "- Do not hallucinate or make up information.\n"
)

_PROMPTS = {
    "information_retrieval": ChatPromptTemplate.from_messages([
        ("system", _BASE_SYSTEM + "\nContext:\n{context}\n\n{tool_context}"),
        ("human", "{question}"),
    ]),
    "summarization": ChatPromptTemplate.from_messages([
        ("system",
         "You are a summarization expert. Create a clear, structured summary of the "
         "provided context. Use bullet points when appropriate.\n"
         "Cite sources using [Source N] notation.\n\n"
         "Context:\n{context}\n\n{tool_context}"),
        ("human", "{question}"),
    ]),
    "comparison": ChatPromptTemplate.from_messages([
        ("system",
         "You are an analytical expert. Compare and contrast the subjects in the query "
         "using ONLY the provided context. Create a structured comparison.\n"
         "Cite sources using [Source N] notation.\n\n"
         "Context:\n{context}\n\n{tool_context}"),
        ("human", "{question}"),
    ]),
    "tool_use": ChatPromptTemplate.from_messages([
        ("system",
         "You are a helpful assistant. Answer the user's question using the tool results "
         "and retrieved context below. Format tool outputs clearly.\n\n"
         "Context:\n{context}\n\n"
         "Tool Results:\n{tool_context}"),
        ("human", "{question}"),
    ]),
}

_MULTI_STEP_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a step-by-step reasoning expert. "
     "Synthesize the intermediate answers into a comprehensive final answer.\n"
     "Cite sources using [Source N] notation.\n\n"
     "Sub-task answers:\n{intermediate}\n\n"
     "Full context:\n{context}\n\n{tool_context}"),
    ("human", "{question}"),
])


@lru_cache(maxsize=1)
def _get_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.3,
    )


def _format_tool_results(tool_results: list[dict]) -> str:
    """Format tool results into readable context for the LLM."""
    if not tool_results:
        return ""
    parts = []
    for r in tool_results:
        tool = r.get("tool", "unknown")
        if r.get("status") == "error":
            parts.append(f"[Tool: {tool}] Error: {r.get('error', 'unknown')}")
        elif tool == "calculator":
            parts.append(f"[Calculator] {r.get('expression', '')} = {r.get('result', 'N/A')}")
        elif tool == "document_search":
            results = r.get("results", [])
            parts.append(f"[Document Search] {len(results)} results found")
            for sr in results[:3]:
                parts.append(f"  - {sr.get('source', 'unknown')}: {sr.get('content', '')[:200]}")
        else:
            parts.append(f"[Tool: {tool}] {json.dumps(r, default=str)[:300]}")
    return "\n".join(parts)


class SynthesisAgent(BaseAgent):
    """Combines retrieved context, tool results, and intermediate answers into a final response."""

    name = "synthesis"
    description = "Generates the final grounded answer with citations"

    def execute(self, ctx: AgentContext) -> AgentContext:
        t0 = time.perf_counter()

        tool_context = _format_tool_results(ctx.tool_results)

        # Select prompt template based on intent
        if ctx.query_type == "multi_step" and ctx.intermediate_answers:
            prompt = _MULTI_STEP_PROMPT
            intermediate_text = "\n\n".join(
                f"Sub-task {i+1}: {ans}" for i, ans in enumerate(ctx.intermediate_answers)
            )
            invoke_args = {
                "question": ctx.query,
                "context": ctx.context_text,
                "intermediate": intermediate_text,
                "tool_context": tool_context,
            }
        else:
            prompt = _PROMPTS.get(ctx.intent, _PROMPTS["information_retrieval"])
            invoke_args = {
                "question": ctx.query,
                "context": ctx.context_text,
                "tool_context": tool_context,
            }

        self._log(ctx, "generate", f"intent={ctx.intent}, prompt={ctx.intent}")

        try:
            llm = _get_llm()
            chain = prompt | llm
            response = chain.invoke(invoke_args)
            answer = response.content  # type: ignore[union-attr]

            # Extract token usage
            token_usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                token_usage = {
                    "prompt_tokens": getattr(um, "input_tokens", 0),
                    "completion_tokens": getattr(um, "output_tokens", 0),
                    "total_tokens": getattr(um, "total_tokens", 0),
                }
            ctx.metadata["token_usage"] = token_usage

        except RuntimeError as exc:
            logger.error("LLM config error: %s", exc)
            ctx.errors.append(str(exc))
            answer = "⚠️ LLM is not configured. Please ensure Ollama is running at " + settings.OLLAMA_BASE_URL
        except Exception as exc:
            logger.exception("LLM generation failed")
            ctx.errors.append(f"Generation failed: {exc}")

            # Fallback: return raw context
            if ctx.retrieved_chunks:
                answer = "⚠️ LLM unavailable. Here are the most relevant passages:\n\n"
                for i, c in enumerate(ctx.retrieved_chunks[:3], 1):
                    answer += f"**[{i}]** {c['content'][:300]}...\n\n"
            else:
                answer = "⚠️ Unable to generate an answer. No context and no LLM available."

        ctx.final_answer = answer
        self._log(ctx, "answer_generated", f"{len(answer)} chars")

        # Compute confidence
        scores = [c.get("reranker_score") or c.get("hybrid_score") or c.get("score", 0)
                  for c in ctx.retrieved_chunks]
        if scores:
            scores_valid = [s for s in scores if s is not None and s > 0]
            ctx.confidence = round(sum(scores_valid) / max(len(scores_valid), 1), 4)
        self._log(ctx, "confidence", f"{ctx.confidence:.4f}")

        # Check if human review needed
        if ctx.confidence < settings.CONFIDENCE_THRESHOLD:
            ctx.requires_human_review = True
            ctx.human_review_reason = f"Low confidence: {ctx.confidence:.4f}"
        if ctx.errors:
            ctx.requires_human_review = True
            ctx.human_review_reason = f"Errors during processing: {len(ctx.errors)}"

        ctx.add_message(AgentMessage(
            role=MessageRole.SYNTHESIS,
            content={
                "answer_length": len(answer),
                "confidence": ctx.confidence,
                "citations": len(ctx.citations),
                "requires_review": ctx.requires_human_review,
            },
        ))

        ctx.latency["synthesis_agent_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return ctx
