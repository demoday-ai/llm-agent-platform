"""Latency-based balancer strategy using exponential moving average."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from src.balancer.base import BalancerStrategy
from src.balancer.round_robin import RoundRobinStrategy

if TYPE_CHECKING:
    from src.providers.models import Provider

_DEFAULT_ALPHA = 0.3


class LatencyBasedStrategy(BalancerStrategy):
    """Selects provider with lowest average latency (EMA)."""

    def __init__(self, alpha: float = _DEFAULT_ALPHA) -> None:
        self._alpha = alpha
        self._averages: dict[str, float] = {}
        self._lock = threading.Lock()
        self._fallback = RoundRobinStrategy()

    def record_latency(self, provider_id: str, latency_seconds: float) -> None:
        """Record observed latency and update EMA for the provider."""
        with self._lock:
            prev = self._averages.get(provider_id)
            if prev is None:
                self._averages[provider_id] = latency_seconds
            else:
                self._averages[provider_id] = (
                    self._alpha * latency_seconds + (1 - self._alpha) * prev
                )

    def get_average(self, provider_id: str) -> float | None:
        """Return current EMA for the provider, or None if no data."""
        with self._lock:
            return self._averages.get(provider_id)

    def select_provider(self, providers: list[Provider]) -> Provider:
        """Pick provider with lowest average latency.

        Falls back to round-robin if no latency data exists for any provider.
        """
        with self._lock:
            scored = [
                (p, self._averages[p.id])
                for p in providers
                if p.id in self._averages
            ]

        if not scored:
            return self._fallback.select_provider(providers)

        scored.sort(key=lambda pair: pair[1])
        return scored[0][0]
