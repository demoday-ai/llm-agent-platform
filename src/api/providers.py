"""CRUD HTTP API on top of existing ProviderRegistry singleton."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.providers.models import Provider, ProviderPricing
from src.providers.registry import provider_registry

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    models: list[str]
    weight: float = 1.0
    priority: int = 0
    pricing: ProviderPricing | None = None


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    weight: float | None = None
    priority: int | None = None
    pricing: ProviderPricing | None = None
    is_active: bool | None = None


@router.post("", response_model=Provider, status_code=201)
async def register_provider(body: ProviderCreate) -> Provider:
    """Register a new LLM provider."""
    provider = Provider(**body.model_dump())
    return await provider_registry.add_provider(provider)


@router.get("", response_model=list[Provider])
async def list_providers() -> list[Provider]:
    """List all providers with health status."""
    return await provider_registry.get_all()


@router.get("/{provider_id}", response_model=Provider)
async def get_provider(provider_id: str) -> Provider:
    """Get a single provider."""
    provider = await provider_registry.get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.put("/{provider_id}", response_model=Provider)
async def update_provider(provider_id: str, body: ProviderUpdate) -> Provider:
    """Update provider configuration (partial update)."""
    existing = await provider_registry.get_provider(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    updates = body.model_dump(exclude_unset=True)
    updated = existing.model_copy(update=updates)

    # Replace in registry atomically
    async with provider_registry._lock:
        provider_registry._providers[provider_id] = updated

    return updated


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: str) -> None:
    """Delete a provider."""
    deleted = await provider_registry.remove_provider(provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
