"""POST /v1/chat/completions - OpenAI-compatible proxy with load balancing."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
import contextlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from src.balancer.router import model_router
from src.core.config import settings
from src.providers.openrouter import OpenRouterClient, UpstreamError
from src.schemas.openai import ChatCompletionRequest  # noqa: TC001

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_guardrails_pipeline():  # noqa: ANN202
    """Lazy import to avoid circular dependency."""
    from src.main import guardrails_pipeline  # noqa: PLC0415
    return guardrails_pipeline


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> StreamingResponse | JSONResponse:
    messages = [m.model_dump(exclude_none=True) for m in request.messages]

    pipeline = _get_guardrails_pipeline()
    block = await pipeline.check_request(messages)
    if block is not None:
        logger.warning("Request blocked: %s", block.reason)
        raise HTTPException(status_code=400, detail=block.reason)

    provider = await model_router.route(request.model)

    api_key = provider.api_key or settings.OPENROUTER_API_KEY
    client = OpenRouterClient(base_url=provider.base_url, api_key=api_key)

    kwargs = {}
    for field in ("temperature", "max_tokens", "top_p", "frequency_penalty",
                  "presence_penalty", "stop"):
        value = getattr(request, field, None)
        if value is not None:
            kwargs[field] = value

    try:
        result = await client.chat_completion(
            messages=messages,
            model=request.model,
            stream=request.stream,
            **kwargs,
        )
    except UpstreamError as exc:
        await client.close()
        raise _map_upstream_error(exc) from exc
    except httpx.TimeoutException as exc:
        await client.close()
        raise HTTPException(status_code=504, detail="Upstream timeout") from exc
    except httpx.ConnectError as exc:
        await client.close()
        raise HTTPException(status_code=502, detail="Cannot connect to upstream") from exc

    if request.stream:
        return StreamingResponse(
            _safe_stream(result, client),  # type: ignore[arg-type]
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    await client.close()
    response_content: dict = result  # type: ignore[assignment]
    text = _extract_response_text(response_content)
    if text:
        masked_text, flagged = await pipeline.check_response(text)
        if flagged is not None:
            response_content = _replace_response_text(response_content, masked_text)

    return JSONResponse(content=response_content)


async def _safe_stream(
    source: AsyncIterator[bytes],
    client: OpenRouterClient,
) -> AsyncIterator[bytes]:
    """Wrap upstream stream; close client when done."""
    try:
        async for chunk in source:
            yield chunk
    except UpstreamError as exc:
        error_payload = {"error": {"message": exc.detail, "code": exc.status_code}}
        yield f"data: {json.dumps(error_payload)}\n\n".encode()
    except httpx.TimeoutException:
        error_payload = {"error": {"message": "Upstream timeout", "code": 504}}
        yield f"data: {json.dumps(error_payload)}\n\n".encode()
    except httpx.ConnectError:
        error_payload = {"error": {"message": "Cannot connect to upstream", "code": 502}}
        yield f"data: {json.dumps(error_payload)}\n\n".encode()
    finally:
        await client.close()


def _map_upstream_error(exc: UpstreamError) -> HTTPException:
    if exc.status_code == 429:
        return HTTPException(status_code=429, detail="Rate limit exceeded")
    if exc.status_code >= 500:
        return HTTPException(status_code=502, detail="Upstream server error")
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _extract_response_text(response: dict) -> str:
    """Extract assistant text from OpenAI-format response."""
    try:
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "") or ""
    except (IndexError, AttributeError, TypeError):
        pass
    return ""


def _replace_response_text(response: dict, new_text: str) -> dict:
    """Return a copy of the response with the first choice's content replaced."""
    import copy  # noqa: PLC0415
    result = copy.deepcopy(response)
    with contextlib.suppress(IndexError, KeyError, TypeError):
        result["choices"][0]["message"]["content"] = new_text
    return result
