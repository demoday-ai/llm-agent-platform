"""POST /v1/embeddings - OpenAI-compatible embedding proxy with load balancing."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.balancer.router import model_router
from src.core.config import settings
from src.providers.openrouter import OpenRouterClient, UpstreamError
from src.schemas.openai import EmbeddingRequest
from src.telemetry.langfuse_tracer import trace_embedding_call
from src.telemetry.metrics import (
    llm_embedding_duration_seconds,
    llm_embedding_requests_total,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/embeddings", response_model=None)
async def embeddings(request: EmbeddingRequest) -> JSONResponse:
    provider = await model_router.route(request.model)

    api_key = provider.api_key or settings.OPENROUTER_API_KEY
    client = OpenRouterClient(base_url=provider.base_url, api_key=api_key)
    t_start = time.monotonic()
    dt_start = datetime.now(timezone.utc)

    try:
        result = await client.embedding(
            input_text=request.input,
            model=request.model,
        )
    except UpstreamError as exc:
        await client.close()
        duration = time.monotonic() - t_start
        llm_embedding_requests_total.labels(
            model=request.model, provider=provider.name, status_code=str(exc.status_code),
        ).inc()
        llm_embedding_duration_seconds.labels(
            model=request.model, provider=provider.name,
        ).observe(duration)
        raise _map_upstream_error(exc) from exc
    except httpx.TimeoutException as exc:
        await client.close()
        raise HTTPException(status_code=504, detail="Upstream timeout") from exc
    except httpx.ConnectError as exc:
        await client.close()
        raise HTTPException(status_code=502, detail="Cannot connect to upstream") from exc

    await client.close()
    dt_end = datetime.now(timezone.utc)
    duration = time.monotonic() - t_start

    llm_embedding_requests_total.labels(
        model=request.model, provider=provider.name, status_code="200",
    ).inc()
    llm_embedding_duration_seconds.labels(
        model=request.model, provider=provider.name,
    ).observe(duration)

    # Langfuse trace
    usage = result.get("usage", {})
    data = result.get("data", [])
    dimensions = len(data[0].get("embedding", [])) if data else 0
    trace_embedding_call(
        model=request.model,
        input_text=request.input,
        dimensions=dimensions,
        duration=duration,
        tokens=usage.get("total_tokens", 0),
        provider=provider.name,
        start_time=dt_start,
        end_time=dt_end,
    )

    return JSONResponse(content=result)


def _map_upstream_error(exc: UpstreamError) -> HTTPException:
    if exc.status_code == 429:
        return HTTPException(status_code=429, detail="Rate limit exceeded")
    if exc.status_code >= 500:
        return HTTPException(status_code=502, detail="Upstream server error")
    return HTTPException(status_code=exc.status_code, detail=exc.detail)
