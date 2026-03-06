"""Tool Execution Agent — runs external tools, search APIs, and data fetchers."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.agents.base import BaseAgent, AgentContext, AgentMessage, MessageRole

logger = logging.getLogger(__name__)


# ── Tool registry ────────────────────────────────────────────

_TOOLS: dict[str, dict] = {}


def register_tool(name: str, description: str, handler: Callable[..., dict]) -> None:
    """Register an external tool for agent use."""
    _TOOLS[name] = {"name": name, "description": description, "handler": handler}
    logger.info("Registered tool: %s", name)


def list_tools() -> list[dict]:
    """List all registered tools."""
    return [{"name": t["name"], "description": t["description"]} for t in _TOOLS.values()]


# ── Built-in tools ───────────────────────────────────────────

def _document_search_tool(query: str, **kwargs: Any) -> dict:
    """Search indexed documents (uses existing retrieval pipeline)."""
    from app.core.retrieval import retrieve_chunks
    result = retrieve_chunks(query, top_k=kwargs.get("top_k", 5))
    return {
        "tool": "document_search",
        "status": "success",
        "results": [
            {"content": c["content"][:300], "source": c.get("source", ""), "score": c.get("score", 0)}
            for c in result["chunks"]
        ],
    }


def _list_documents_tool(**kwargs: Any) -> dict:
    """List all indexed documents."""
    try:
        from app.core.vector_store import get_qdrant_client
        from app.config import settings
        client = get_qdrant_client()
        collection = client.get_collection(settings.QDRANT_COLLECTION)
        return {
            "tool": "list_documents",
            "status": "success",
            "total_points": collection.points_count,
            "collection": settings.QDRANT_COLLECTION,
        }
    except Exception as exc:
        return {"tool": "list_documents", "status": "error", "error": str(exc)}


def _system_health_tool(**kwargs: Any) -> dict:
    """Get system health status."""
    from app.config import settings
    status = {"app": settings.APP_NAME, "version": settings.APP_VERSION}

    try:
        from app.core.vector_store import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        status["qdrant"] = "ok"
    except Exception:
        status["qdrant"] = "unreachable"

    try:
        from app.core.cache import is_redis_available
        status["redis"] = "ok" if is_redis_available() else "unavailable"
    except Exception:
        status["redis"] = "unknown"

    return {"tool": "system_health", "status": "success", **status}


def _calculate_tool(expression: str, **kwargs: Any) -> dict:
    """Safe math evaluator for simple expressions."""
    import ast
    import operator

    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            if op_type in ops:
                return ops[op_type](left, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval(tree.body)
        return {"tool": "calculator", "status": "success", "expression": expression, "result": result}
    except Exception as exc:
        return {"tool": "calculator", "status": "error", "error": str(exc)}


# ── Register built-ins ───────────────────────────────────────

def _register_builtins() -> None:
    register_tool("document_search", "Search indexed documents", _document_search_tool)
    register_tool("list_documents", "List all indexed documents", _list_documents_tool)
    register_tool("system_health", "Check system health", _system_health_tool)
    register_tool("calculator", "Evaluate math expressions", _calculate_tool)


_register_builtins()


# ── Tool selection heuristic ─────────────────────────────────

def _select_tools(query: str, intent: str) -> list[str]:
    """Determine which tools are needed based on the query."""
    q = query.lower()
    tools_needed = []

    if any(kw in q for kw in ["calculate", "compute", "math", "what is", "how much"]):
        # Check if it actually looks like math
        import re
        if re.search(r"\d+\s*[\+\-\*/\^]\s*\d+", q):
            tools_needed.append("calculator")

    if any(kw in q for kw in ["list documents", "what documents", "what files", "show files"]):
        tools_needed.append("list_documents")

    if any(kw in q for kw in ["system health", "system status", "is the system"]):
        tools_needed.append("system_health")

    # Always include document search as fallback for tool queries
    if intent == "tool_use" and not tools_needed:
        tools_needed.append("document_search")

    return tools_needed


# ── Tool Agent ───────────────────────────────────────────────

class ToolAgent(BaseAgent):
    """Executes external tools and returns formatted results."""

    name = "tool"
    description = "Executes external tools, search APIs, and data fetchers"

    def execute(self, ctx: AgentContext) -> AgentContext:
        t0 = time.perf_counter()

        tools_needed = _select_tools(ctx.query, ctx.intent)

        if not tools_needed:
            self._log(ctx, "no_tools", "No tools required for this query")
            ctx.latency["tool_agent_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return ctx

        self._log(ctx, "tools_selected", ", ".join(tools_needed))

        for tool_name in tools_needed:
            tool_def = _TOOLS.get(tool_name)
            if not tool_def:
                ctx.errors.append(f"Unknown tool: {tool_name}")
                continue

            self._log(ctx, "execute_tool", tool_name)

            try:
                # Pass query as first arg for tools that accept it
                handler = tool_def["handler"]
                if tool_name == "calculator":
                    # Extract math expression from query
                    import re
                    match = re.search(r'[\d\.\+\-\*/\^\(\)\s]+', ctx.query)
                    expr = match.group(0).strip() if match else ctx.query
                    result = handler(expression=expr)
                elif tool_name in ("document_search",):
                    result = handler(query=ctx.query)
                else:
                    result = handler()

                ctx.tool_results.append(result)
                self._log(ctx, "tool_result", f"{tool_name}: {result.get('status', 'unknown')}")
            except Exception as exc:
                ctx.errors.append(f"Tool {tool_name} failed: {exc}")
                ctx.tool_results.append({
                    "tool": tool_name,
                    "status": "error",
                    "error": str(exc),
                })
                logger.error("Tool %s failed: %s", tool_name, exc)

        ctx.add_message(AgentMessage(
            role=MessageRole.TOOL,
            content={"tools_executed": tools_needed, "results": ctx.tool_results},
        ))

        ctx.latency["tool_agent_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return ctx
