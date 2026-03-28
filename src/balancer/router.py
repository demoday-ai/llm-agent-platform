"""Model router - maps model names to providers via balancer strategy.

Integrates health-aware filtering, circuit breaker, and latency-based selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from src.balancer.circuit_breaker import CircuitBreaker
from src.balancer.health_aware import filter_healthy
from src.balancer.latency_based import LatencyBasedStrategy
from src.providers.registry import provider_registry

if TYPE_CHECKING:
    from src.balancer.base import BalancerStrategy
    from src.providers.models import Provider
    from src.providers.registry import ProviderRegistry


class ModelRouter:
    """Routes model requests to providers using a configured strategy.

    Pipeline: health filter -> circuit breaker filter -> strategy selection.
    """

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        strategy: BalancerStrategy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._registry = registry or provider_registry
        self._strategy = strategy or LatencyBasedStrategy()
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    @property
    def strategy(self) -> BalancerStrategy:
        return self._strategy

    async def route(self, model: str) -> Provider:
        """Select a provider for the given model.

        Pipeline:
        1. Get active providers from registry
        2. Apply health-aware filter
        3. Filter by circuit breaker availability
        4. Apply strategy selection

        Raises HTTPException 404 if no providers serve this model.
        Raises HTTPException 503 if all providers are circuit-broken.
        """
        providers = await self._registry.get_providers_for_model(model)
        if not providers:
            raise HTTPException(
                status_code=404,
                detail=f"No providers available for model: {model}",
            )

        # Step 1: health-aware filter
        providers = filter_healthy(providers)

        # Step 2: circuit breaker filter
        available = [
            p for p in providers if self._circuit_breaker.is_available(p.id)
        ]
        if not available:
            raise HTTPException(
                status_code=503,
                detail=f"All providers for model {model} are circuit-broken",
            )

        return self._strategy.select_provider(available)

    def record_success(self, provider_id: str, latency_seconds: float) -> None:
        """Record a successful request for the provider."""
        self._circuit_breaker.record_success(provider_id)
        if isinstance(self._strategy, LatencyBasedStrategy):
            self._strategy.record_latency(provider_id, latency_seconds)

    def record_failure(self, provider_id: str) -> None:
        """Record a failed request for the provider."""
        self._circuit_breaker.record_failure(provider_id)


model_router = ModelRouter()
