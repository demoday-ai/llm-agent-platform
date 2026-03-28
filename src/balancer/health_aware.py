"""Health-aware provider filter.

Not a balancer strategy itself - applied before strategy selection
to exclude unhealthy providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.providers.models import Provider


def filter_healthy(providers: list[Provider]) -> list[Provider]:
    """Filter providers by health status.

    Returns only healthy providers. If none are healthy, returns
    degraded ones as a fallback. If none are degraded either,
    returns the original list unchanged (let the caller decide).
    """
    healthy = [p for p in providers if p.health_status == "healthy"]
    if healthy:
        return healthy

    degraded = [p for p in providers if p.health_status == "degraded"]
    if degraded:
        return degraded

    return providers
