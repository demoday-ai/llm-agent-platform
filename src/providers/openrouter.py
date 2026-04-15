"""OpenRouter API client for proxying chat completion requests."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 30.0


class OpenRouterClient:
    """Async client for OpenRouter API."""

    def __init__(
        self,
        base_url: str = OPENROUTER_BASE_URL,
        api_key: str = "",
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
        )

    def _headers(self) -> dict[str, str]:
        key = self._api_key or settings.OPENROUTER_API_KEY
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[bytes]:
        """Send chat completion request to OpenRouter.

        For stream=False: returns parsed JSON response.
        For stream=True: returns async generator yielding raw SSE bytes.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        for key in ("temperature", "max_tokens", "top_p", "frequency_penalty",
                     "presence_penalty", "stop", "tools", "tool_choice"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        if stream:
            return self._stream_generator(payload)
        return await self._non_stream_completion(payload)

    async def _non_stream_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(
            "/chat/completions",
            json=payload,
            headers=self._headers(),
        )
        _raise_for_upstream_status(response)
        result: dict[str, Any] = response.json()
        return result

    async def _stream_generator(self, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=payload,
            headers=self._headers(),
        ) as response:
            _raise_for_upstream_status(response)
            async for line in response.aiter_lines():
                if line:
                    yield f"{line}\n\n".encode()

    async def embedding(
        self,
        input_text: str | list[str],
        model: str,
    ) -> dict[str, Any]:
        """Send embedding request to OpenRouter. Returns parsed JSON response."""
        payload: dict[str, Any] = {
            "model": model,
            "input": input_text,
        }
        response = await self._client.post(
            "/embeddings",
            json=payload,
            headers=self._headers(),
        )
        _raise_for_upstream_status(response)
        result: dict[str, Any] = response.json()
        return result

    async def close(self) -> None:
        await self._client.aclose()


class UpstreamError(Exception):
    """Error from upstream OpenRouter API."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Upstream returned {status_code}: {detail}")


def _raise_for_upstream_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        try:
            detail = response.text
        except httpx.ResponseNotRead:
            detail = f"HTTP {response.status_code}"
        raise UpstreamError(response.status_code, detail)


openrouter_client = OpenRouterClient()
