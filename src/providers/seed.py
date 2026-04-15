"""Seed initial providers into the registry."""

from __future__ import annotations

from src.providers.models import Provider
from src.providers.registry import provider_registry

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

SEED_PROVIDERS: list[Provider] = [
    Provider(
        name="StepFun Step 3.5 Flash",
        base_url=OPENROUTER_BASE,
        models=["stepfun/step-3.5-flash"],
        weight=1.0,
    ),
    Provider(
        name="NVIDIA Nemotron 3 Super",
        base_url=OPENROUTER_BASE,
        models=["nvidia/nemotron-3-super"],
        weight=1.0,
    ),
    Provider(
        name="DeepSeek V3.2",
        base_url=OPENROUTER_BASE,
        models=["deepseek/deepseek-chat", "deepseek/deepseek-v3.2"],
        weight=1.0,
    ),
    Provider(
        name="OpenAI gpt-oss-120b",
        base_url=OPENROUTER_BASE,
        models=["openai/gpt-oss-120b"],
        weight=1.0,
    ),
    Provider(
        name="xAI Grok 4.1 Fast",
        base_url=OPENROUTER_BASE,
        models=["x-ai/grok-4.1-fast"],
        weight=1.0,
    ),
    Provider(
        name="Google Gemini 2.5 Flash Lite",
        base_url=OPENROUTER_BASE,
        models=["google/gemini-2.5-flash-lite"],
        weight=1.0,
    ),
    Provider(
        name="Google Gemini Embedding 001",
        base_url=OPENROUTER_BASE,
        models=["google/gemini-embedding-001"],
        weight=1.0,
    ),
]


async def seed_providers() -> None:
    """Register all seed providers."""
    for provider in SEED_PROVIDERS:
        await provider_registry.add_provider(provider)
