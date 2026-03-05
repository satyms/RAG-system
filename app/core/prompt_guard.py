"""Prompt injection defense — detect and block malicious prompts."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Known attack patterns ────────────────────────────────────
_INJECTION_PATTERNS: list[re.Pattern] = [
    # System prompt override attempts
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"override\s+(system|your)\s+(prompt|instructions|rules)", re.IGNORECASE),

    # Role hijacking
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an|if|though)\s+", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
    re.compile(r"switch\s+to\s+.{0,20}mode", re.IGNORECASE),

    # System prompt extraction
    re.compile(r"(show|print|reveal|display|output)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"repeat\s+(your|the)\s+(system\s+)?(prompt|instructions)", re.IGNORECASE),

    # Jailbreak patterns
    re.compile(r"DAN\s*mode", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+(enabled|on|output)", re.IGNORECASE),
    re.compile(r"bypass\s+(your|all|any)\s+(safety|content|ethical)\s+(filter|restriction|guideline)", re.IGNORECASE),

    # Markdown/code injection
    re.compile(r"```\s*(system|assistant)\s*\n", re.IGNORECASE),

    # Delimiter injection
    re.compile(r"<\|?(system|im_start|im_end|endoftext)\|?>", re.IGNORECASE),
]

# ── Suspicious context patterns (for retrieved chunks) ───────
_CONTEXT_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+the\s+(above|context|instructions)", re.IGNORECASE),
    re.compile(r"new\s+instructions?:\s*", re.IGNORECASE),
    re.compile(r"(system|assistant)\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start)\|?>", re.IGNORECASE),
]


@dataclass
class InjectionResult:
    """Result of a prompt injection check."""
    is_suspicious: bool = False
    blocked: bool = False
    patterns_matched: list[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 = safe, 1.0 = definitely malicious


def check_prompt_injection(query: str) -> InjectionResult:
    """
    Analyse a user query for prompt injection attempts.

    Returns an InjectionResult with risk assessment.
    """
    result = InjectionResult()
    matched = []

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            matched.append(pattern.pattern)

    if matched:
        result.is_suspicious = True
        result.patterns_matched = matched
        result.risk_score = min(1.0, len(matched) * 0.3)

        # Block if risk is high enough (2+ patterns or certain patterns)
        if result.risk_score >= 0.6:
            result.blocked = True

        logger.warning(
            "Prompt injection detected",
            extra={
                "query_preview": query[:100],
                "patterns_matched": len(matched),
                "risk_score": result.risk_score,
                "blocked": result.blocked,
            },
        )

    return result


def filter_context_injections(chunks: list[dict]) -> list[dict]:
    """
    Remove or flag chunks that contain potential instruction injection.

    Filters out chunks whose content matches known injection patterns.
    """
    safe_chunks = []
    removed = 0

    for chunk in chunks:
        content = chunk.get("content", "")
        is_safe = True

        for pattern in _CONTEXT_INJECTION_PATTERNS:
            if pattern.search(content):
                is_safe = False
                removed += 1
                logger.warning(
                    "Context injection filtered",
                    extra={
                        "chunk_id": chunk.get("id", "unknown"),
                        "source": chunk.get("source", "unknown"),
                        "pattern": pattern.pattern,
                    },
                )
                break

        if is_safe:
            safe_chunks.append(chunk)

    if removed:
        logger.info("Filtered %d chunks with potential context injection", removed)

    return safe_chunks


def sanitize_query(query: str) -> str:
    """
    Clean user query input — strip control characters, normalise whitespace.

    Does NOT block; use check_prompt_injection() for blocking decisions.
    """
    # Remove null bytes and control characters
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", query)
    # Normalise whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
