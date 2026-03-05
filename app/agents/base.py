"""Agent base class and registry — defines communication protocol and routing."""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Message protocol ─────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    PLANNER = "planner"
    RETRIEVAL = "retrieval"
    TOOL = "tool"
    SYNTHESIS = "synthesis"
    SYSTEM = "system"


@dataclass
class AgentMessage:
    """Standardised message passed between agents."""
    role: MessageRole
    content: Any
    metadata: dict = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    parent_id: str | None = None  # traces message chain


@dataclass
class AgentContext:
    """Shared context object passed through the agent pipeline."""
    query: str
    original_query: str = ""
    query_type: str = "simple"           # simple | complex | tool_required | multi_step
    intent: str = "information_retrieval" # information_retrieval | summarization | comparison | tool_use
    complexity: str = "low"              # low | medium | high
    sub_tasks: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    context_text: str = ""
    tool_results: list[dict] = field(default_factory=list)
    intermediate_answers: list[str] = field(default_factory=list)
    final_answer: str = ""
    citations: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    reasoning_steps: list[dict] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    latency: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    debug_info: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    human_review_reason: str = ""

    def add_step(self, agent: str, action: str, details: str = "") -> None:
        """Record a reasoning step for explainability."""
        self.reasoning_steps.append({
            "agent": agent,
            "action": action,
            "details": details,
            "timestamp": time.time(),
        })

    def add_message(self, msg: AgentMessage) -> None:
        self.messages.append(msg)


# ── Base Agent ───────────────────────────────────────────────

class BaseAgent(ABC):
    """Abstract base class for all agents."""

    name: str = "base"
    description: str = ""

    @abstractmethod
    def execute(self, ctx: AgentContext) -> AgentContext:
        """Execute the agent's logic and return updated context."""
        ...

    def _log(self, ctx: AgentContext, action: str, detail: str = "") -> None:
        ctx.add_step(self.name, action, detail)
        ctx.debug_info.append(f"[{self.name}] {action}: {detail}")
        logger.info("[%s] %s — %s", self.name, action, detail)


# ── Agent Registry ───────────────────────────────────────────

class AgentRegistry:
    """Central registry of available agents."""

    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        cls._agents[agent.name] = agent
        logger.info("Registered agent: %s", agent.name)

    @classmethod
    def get(cls, name: str) -> BaseAgent | None:
        return cls._agents.get(name)

    @classmethod
    def list_agents(cls) -> list[str]:
        return list(cls._agents.keys())

    @classmethod
    def clear(cls) -> None:
        cls._agents.clear()
