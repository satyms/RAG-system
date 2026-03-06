"""Planner Agent — analyses queries, classifies intent, decomposes complex queries."""

from __future__ import annotations

import logging
import time
import json
from functools import lru_cache

from app.agents.base import BaseAgent, AgentContext, AgentMessage, MessageRole
from app.config import settings

logger = logging.getLogger(__name__)

# ── Query classification keywords / heuristics ───────────────

_COMPARISON_KEYWORDS = [
    "compare", "contrast", "difference", "versus", "vs", "between",
    "similarities", "differ", "pros and cons", "advantage", "disadvantage",
]
_SUMMARIZATION_KEYWORDS = [
    "summarize", "summary", "overview", "brief", "tldr", "tl;dr",
    "key points", "main ideas", "highlights",
]
_MULTI_STEP_KEYWORDS = [
    "step by step", "explain how", "walk me through", "process of",
    "first", "then", "finally", "how does .* work",
]
_TOOL_KEYWORDS = [
    "search for", "look up", "find on the web", "latest", "current",
    "today's", "real-time", "calculate", "compute",
]


def _classify_intent(query: str) -> str:
    """Classify query intent using keyword heuristics."""
    q = query.lower()
    if any(kw in q for kw in _COMPARISON_KEYWORDS):
        return "comparison"
    if any(kw in q for kw in _SUMMARIZATION_KEYWORDS):
        return "summarization"
    if any(kw in q for kw in _TOOL_KEYWORDS):
        return "tool_use"
    return "information_retrieval"


def _classify_complexity(query: str) -> str:
    """Estimate query complexity: low / medium / high."""
    q = query.lower()
    word_count = len(q.split())

    # High complexity: multi-step, comparison, very long
    if word_count > 40 or any(kw in q for kw in _MULTI_STEP_KEYWORDS):
        return "high"
    if any(kw in q for kw in _COMPARISON_KEYWORDS) or word_count > 20:
        return "medium"
    return "low"


def _classify_query_type(intent: str, complexity: str) -> str:
    """Map intent + complexity → routing type."""
    if intent == "tool_use":
        return "tool_required"
    if complexity == "high":
        return "multi_step"
    if complexity == "medium":
        return "complex"
    return "simple"


def _decompose_query_heuristic(query: str) -> list[str]:
    """Decompose a complex query into sub-tasks using simple heuristics."""
    q = query.lower()

    # Try splitting on conjunctions / "and" / "also"
    sub_tasks = []

    # Split on common conjunctions
    parts = [p.strip() for p in q.replace(" and also ", "|").replace(" and ", "|").replace("; ", "|").split("|")]
    parts = [p for p in parts if len(p) > 10]

    if len(parts) > 1:
        return parts

    # For comparison queries, extract the two subjects
    for kw in ["compare", "vs", "versus"]:
        if kw in q:
            pieces = q.split(kw, 1)
            if len(pieces) == 2 and len(pieces[1].strip()) > 3:
                sub_tasks.append(f"Retrieve information about {pieces[0].strip()}")
                sub_tasks.append(f"Retrieve information about {pieces[1].strip()}")
                sub_tasks.append(f"Compare the two")
                return sub_tasks

    return [query]  # Can't decompose → single task


def _decompose_query_llm(query: str) -> list[str]:
    """Use LLM to decompose a query into sub-tasks."""
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Break the following query into 2-5 independent sub-questions that can be "
             "answered separately and then combined. Return ONLY a JSON array of strings.\n"
             "If the query is already simple, return a single-element array."),
            ("human", "{query}"),
        ])

        llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
        )

        response = (prompt | llm).invoke({"query": query})
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tasks = json.loads(raw)
        if isinstance(tasks, list) and all(isinstance(t, str) for t in tasks):
            return tasks
    except Exception as exc:
        logger.warning("LLM decomposition failed, using heuristic: %s", exc)

    return _decompose_query_heuristic(query)


# ── Planner Agent ────────────────────────────────────────────

class PlannerAgent(BaseAgent):
    """Analyzes user queries, classifies intent, determines strategy, decomposes sub-tasks."""

    name = "planner"
    description = "Analyzes queries and creates execution plans"

    def execute(self, ctx: AgentContext) -> AgentContext:
        t0 = time.perf_counter()

        self._log(ctx, "analyse_query", f"Processing: {ctx.query[:80]}")

        # 1. Classify intent
        ctx.intent = _classify_intent(ctx.query)
        self._log(ctx, "classify_intent", ctx.intent)

        # 2. Classify complexity
        ctx.complexity = _classify_complexity(ctx.query)
        self._log(ctx, "classify_complexity", ctx.complexity)

        # 3. Determine query type for routing
        ctx.query_type = _classify_query_type(ctx.intent, ctx.complexity)
        self._log(ctx, "determine_routing", f"type={ctx.query_type}")

        # 4. Decompose if complex/multi-step
        if ctx.query_type in ("complex", "multi_step"):
            if ctx.complexity == "high":
                ctx.sub_tasks = _decompose_query_llm(ctx.query)
            else:
                ctx.sub_tasks = _decompose_query_heuristic(ctx.query)
            self._log(ctx, "decompose", f"{len(ctx.sub_tasks)} sub-tasks")
        else:
            ctx.sub_tasks = [ctx.query]

        # 5. Determine required agents
        agents_needed = ["retrieval", "synthesis"]
        if ctx.query_type == "tool_required":
            agents_needed.insert(1, "tool")
        ctx.metadata["agents_needed"] = agents_needed
        self._log(ctx, "plan_agents", ", ".join(agents_needed))

        # Record message
        ctx.add_message(AgentMessage(
            role=MessageRole.PLANNER,
            content={
                "intent": ctx.intent,
                "complexity": ctx.complexity,
                "query_type": ctx.query_type,
                "sub_tasks": ctx.sub_tasks,
                "agents_needed": agents_needed,
            },
        ))

        ctx.latency["planner_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return ctx
