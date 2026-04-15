"""Langfuse integration for LLM-specific tracing.

If Langfuse is not configured (LANGFUSE_PUBLIC_KEY is empty),
all functions silently no-op.
"""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import settings

logger = logging.getLogger(__name__)

_langfuse: Any | None = None


def _get_client() -> Any | None:
    """Lazy-init the Langfuse client. Returns None when not configured."""
    global _langfuse  # noqa: PLW0603

    if _langfuse is not None:
        return _langfuse

    if not settings.LANGFUSE_PUBLIC_KEY:
        return None

    try:
        from langfuse import Langfuse  # type: ignore[import-untyped]

        _langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse client initialized (host=%s)", settings.LANGFUSE_HOST)
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)
        return None

    return _langfuse


def trace_llm_call(
    *,
    model: str,
    messages: list[dict[str, str]],
    response: str,
    duration: float,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    provider: str = "",
    session_id: str | None = None,
) -> None:
    """Record an LLM call in Langfuse.

    Creates: Session -> Trace -> Span -> Event hierarchy.
    Silently returns if Langfuse is not configured or unavailable.
    """
    client = _get_client()
    if client is None:
        return

    try:
        trace = client.trace(
            name="llm-call",
            session_id=session_id,
            metadata={"provider": provider},
        )

        trace.generation(
            name="chat-completion",
            model=model,
            input=messages,
            output=response,
            usage={
                "input": tokens_in,
                "output": tokens_out,
                "total": tokens_in + tokens_out,
            },
            metadata={"provider": provider, "duration_s": duration},
        )
    except Exception:
        logger.warning("Failed to send trace to Langfuse", exc_info=True)


def trace_embedding_call(
    *,
    model: str,
    input_text: str | list[str],
    dimensions: int,
    duration: float,
    tokens: int,
    provider: str = "",
) -> None:
    """Record an embedding call in Langfuse."""
    client = _get_client()
    if client is None:
        return

    try:
        input_preview = input_text[:200] if isinstance(input_text, str) else str(input_text[:2])[:200]
        trace = client.trace(
            name="embedding-call",
            metadata={"provider": provider},
        )

        trace.generation(
            name="embedding",
            model=model,
            input=input_preview,
            output={"dimensions": dimensions},
            usage={
                "input": tokens,
                "total": tokens,
            },
            metadata={"provider": provider, "duration_s": duration, "dimensions": dimensions},
        )
    except Exception:
        logger.warning("Failed to send embedding trace to Langfuse", exc_info=True)
