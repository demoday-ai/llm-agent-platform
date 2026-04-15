"""Prompt injection detection guardrail."""

from __future__ import annotations

import re

from src.guardrails.base import Guardrail, GuardrailResult

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+previous",
        r"disregard\s+above",
        r"system\s+prompt",
        r"you\s+are\s+now",
        r"act\s+as",
        r"pretend\s+you",
        r"reveal\s+your\s+instructions",
        r"what\s+are\s+your\s+instructions",
    )
)

GUARDRAIL_NAME = "prompt_injection"


class PromptInjectionGuardrail(Guardrail):
    """Detect common prompt injection patterns in user messages."""

    async def check_request(self, messages: list[dict]) -> GuardrailResult:
        for msg in messages:
            # Only check user messages - system prompts may legitimately mention injection patterns
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            for pattern in _INJECTION_PATTERNS:
                match = pattern.search(content)
                if match:
                    return GuardrailResult(
                        passed=False,
                        reason=f"Prompt injection detected: '{match.group()}'",
                        guardrail_name=GUARDRAIL_NAME,
                    )
        return GuardrailResult(passed=True, guardrail_name=GUARDRAIL_NAME)

    async def check_response(self, content: str) -> GuardrailResult:
        return GuardrailResult(passed=True, guardrail_name=GUARDRAIL_NAME)
