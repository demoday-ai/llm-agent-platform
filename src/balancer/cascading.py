"""Cascading strategy - start cheap, escalate on low quality.

Inspired by X5 Tech lecture on cost-efficient LLM routing.
Tries the cheapest model first, escalates to more expensive ones
if the response quality is insufficient.
"""

from __future__ import annotations

from typing import Any

_MIN_TOKEN_THRESHOLD = 10


async def cascade(
    models: list[str],
    messages: list[dict[str, Any]],
    call_fn: Any,
    threshold: float = 0.7,  # noqa: ARG001 - reserved for future confidence scoring
) -> tuple[str, Any]:
    """Try models in order (cheapest first), escalate on low quality.

    Args:
        models: Ordered list of model names (cheapest first).
        messages: Chat messages to send.
        call_fn: Async callable(model, messages) -> response dict.
            Expected response shape: {"content": str, "usage": {...}}.
        threshold: Confidence threshold (reserved for future use).

    Returns:
        Tuple of (model_used, response).

    Raises:
        RuntimeError: If all models fail or produce low quality responses.
    """
    last_error: Exception | None = None

    for model in models:
        try:
            response = await call_fn(model, messages)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

        content = response.get("content", "") if isinstance(response, dict) else ""
        token_count = len(content.split()) if content else 0

        if token_count >= _MIN_TOKEN_THRESHOLD:
            return model, response

        # Response too short, try next model
        last_error = None

    msg = "All models in cascade failed or produced low quality responses"
    if last_error is not None:
        raise RuntimeError(msg) from last_error
    raise RuntimeError(msg)
