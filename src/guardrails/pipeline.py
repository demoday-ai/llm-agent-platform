"""Guardrails pipeline - runs all guardrails in sequence."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.guardrails.secret_leak import mask_secrets

if TYPE_CHECKING:
    from src.guardrails.base import Guardrail, GuardrailResult

logger = logging.getLogger(__name__)


class GuardrailsPipeline:
    """Run a list of guardrails on requests and responses."""

    def __init__(self, guardrails: list[Guardrail], *, enabled: bool = True) -> None:
        self._guardrails = list(guardrails)
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def check_request(self, messages: list[dict]) -> GuardrailResult | None:
        """Run all guardrails on request messages. Returns first failure or None if all passed."""
        if not self._enabled:
            return None
        for guardrail in self._guardrails:
            result = await guardrail.check_request(messages)
            if not result.passed:
                logger.warning(
                    "Request blocked by %s: %s", result.guardrail_name, result.reason,
                )
                return result
        return None

    async def check_response(self, content: str) -> tuple[str, GuardrailResult | None]:
        """Run all guardrails on response content.

        Returns (possibly masked content, first failure result or None).
        """
        if not self._enabled:
            return content, None

        masked_content = content
        for guardrail in self._guardrails:
            result = await guardrail.check_response(masked_content)
            if not result.passed:
                logger.warning(
                    "Response flagged by %s: %s", result.guardrail_name, result.reason,
                )
                masked_content, _detections = mask_secrets(masked_content)
                return masked_content, result

        return masked_content, None
