"""Shared HTTP client for agent <-> platform communication."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 10
_INITIAL_BACKOFF = 2.0
_BACKOFF_FACTOR = 1.5


class PlatformClient:
    """Client that registers an agent on the platform and proxies LLM calls."""

    def __init__(
        self,
        platform_url: str,
        master_token: str,
        agent_name: str,
        agent_description: str,
        methods: list[str],
        endpoint_url: str,
    ) -> None:
        self._platform_url = platform_url.rstrip("/")
        self._master_token = master_token
        self._agent_name = agent_name
        self._agent_description = agent_description
        self._methods = methods
        self._endpoint_url = endpoint_url
        self._agent_token: str | None = None
        self._client = httpx.AsyncClient(timeout=60.0)

    async def register(self) -> str:
        """Register agent on the platform with retry+backoff. Returns agent token."""
        backoff = _INITIAL_BACKOFF
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await self._client.post(
                    f"{self._platform_url}/agents",
                    json={
                        "name": self._agent_name,
                        "description": self._agent_description,
                        "methods": self._methods,
                        "endpoint_url": self._endpoint_url,
                    },
                    headers={"Authorization": f"Bearer {self._master_token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                self._agent_token = data["token"]
                logger.info(
                    "Agent '%s' registered (id=%s, attempt=%d)",
                    self._agent_name,
                    data["id"],
                    attempt,
                )
                return self._agent_token
            except Exception:
                logger.warning(
                    "Registration attempt %d/%d failed, retrying in %.1fs",
                    attempt,
                    _MAX_RETRIES,
                    backoff,
                    exc_info=True,
                )
                await asyncio.sleep(backoff)
                backoff *= _BACKOFF_FACTOR

        msg = f"Failed to register agent '{self._agent_name}' after {_MAX_RETRIES} attempts"
        raise RuntimeError(msg)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str = "deepseek/deepseek-chat",
        stream: bool = False,
    ) -> dict[str, Any] | AsyncGenerator[bytes, None]:
        """Send chat completion request through the platform proxy."""
        if self._agent_token is None:
            msg = "Agent not registered yet, call register() first"
            raise RuntimeError(msg)

        headers = {"Authorization": f"Bearer {self._agent_token}"}
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        if stream:
            return self._stream_chat(headers, payload)

        resp = await self._client.post(
            f"{self._platform_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def _stream_chat(
        self,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> AsyncGenerator[bytes, None]:
        async with self._client.stream(
            "POST",
            f"{self._platform_url}/v1/chat/completions",
            json=payload,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk

    async def close(self) -> None:
        """Cleanup underlying HTTP client."""
        await self._client.aclose()
