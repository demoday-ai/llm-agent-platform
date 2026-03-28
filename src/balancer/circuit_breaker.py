"""Circuit breaker per provider.

States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing).
All timestamps use time.monotonic() for monotonicity guarantees.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

STATE_CLOSED = "closed"
STATE_OPEN = "open"
STATE_HALF_OPEN = "half_open"

_DEFAULT_ERROR_THRESHOLD = 5
_DEFAULT_COOLDOWN_SECONDS = 30.0
_DEFAULT_WINDOW_SECONDS = 60.0


@dataclass
class _ProviderState:
    """Mutable per-provider circuit state."""

    state: str = STATE_CLOSED
    failures: list[float] = field(default_factory=list)  # monotonic timestamps
    opened_at: float = 0.0
    half_open_in_flight: bool = False


class CircuitBreaker:
    """Time-based circuit breaker tracking errors per provider."""

    def __init__(
        self,
        error_threshold: int | None = None,
        cooldown_seconds: float | None = None,
        window_seconds: float | None = None,
    ) -> None:
        self._error_threshold = error_threshold or int(
            os.environ.get("CB_ERROR_THRESHOLD", str(_DEFAULT_ERROR_THRESHOLD))
        )
        self._cooldown_seconds = cooldown_seconds or float(
            os.environ.get("CB_COOLDOWN_SECONDS", str(_DEFAULT_COOLDOWN_SECONDS))
        )
        self._window_seconds = window_seconds or float(
            os.environ.get("CB_WINDOW_SECONDS", str(_DEFAULT_WINDOW_SECONDS))
        )
        self._states: dict[str, _ProviderState] = {}
        self._lock = threading.Lock()

    def _get_state(self, provider_id: str) -> _ProviderState:
        if provider_id not in self._states:
            self._states[provider_id] = _ProviderState()
        return self._states[provider_id]

    def _prune_old_failures(self, ps: _ProviderState, now: float) -> None:
        cutoff = now - self._window_seconds
        ps.failures = [t for t in ps.failures if t > cutoff]

    def record_success(self, provider_id: str) -> None:
        """Record a successful request. Resets circuit if in HALF_OPEN."""
        with self._lock:
            ps = self._get_state(provider_id)
            if ps.state == STATE_HALF_OPEN:
                ps.state = STATE_CLOSED
                ps.failures.clear()
                ps.half_open_in_flight = False
            elif ps.state == STATE_CLOSED:
                now = time.monotonic()
                self._prune_old_failures(ps, now)

    def record_failure(self, provider_id: str) -> None:
        """Record a failed request. May trip circuit to OPEN."""
        now = time.monotonic()
        with self._lock:
            ps = self._get_state(provider_id)

            if ps.state == STATE_HALF_OPEN:
                ps.state = STATE_OPEN
                ps.opened_at = now
                ps.half_open_in_flight = False
                return

            ps.failures.append(now)
            self._prune_old_failures(ps, now)

            if len(ps.failures) >= self._error_threshold:
                ps.state = STATE_OPEN
                ps.opened_at = now

    def is_available(self, provider_id: str) -> bool:
        """Check if the provider is available for requests."""
        now = time.monotonic()
        with self._lock:
            ps = self._get_state(provider_id)

            if ps.state == STATE_CLOSED:
                return True

            if ps.state == STATE_OPEN:
                if now - ps.opened_at >= self._cooldown_seconds:
                    ps.state = STATE_HALF_OPEN
                    ps.half_open_in_flight = False
                    return self._try_half_open_probe(ps)
                return False

            # HALF_OPEN: allow one probe
            return self._try_half_open_probe(ps)

    def _try_half_open_probe(self, ps: _ProviderState) -> bool:
        """Allow exactly one probe request in HALF_OPEN state."""
        if not ps.half_open_in_flight:
            ps.half_open_in_flight = True
            return True
        return False

    def get_state(self, provider_id: str) -> str:
        """Return current state string: 'closed', 'open', or 'half_open'."""
        now = time.monotonic()
        with self._lock:
            ps = self._get_state(provider_id)
            if ps.state == STATE_OPEN and now - ps.opened_at >= self._cooldown_seconds:
                ps.state = STATE_HALF_OPEN
                ps.half_open_in_flight = False
            return ps.state
