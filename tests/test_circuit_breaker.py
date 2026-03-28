"""Unit tests for circuit breaker state machine."""

from __future__ import annotations

import time
from unittest.mock import patch

from src.balancer.circuit_breaker import (
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
    CircuitBreaker,
)


class TestCircuitBreakerClosed:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker(error_threshold=3, cooldown_seconds=10, window_seconds=60)
        assert cb.get_state("p1") == STATE_CLOSED
        assert cb.is_available("p1") is True

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(error_threshold=3, cooldown_seconds=10, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")
        assert cb.get_state("p1") == STATE_CLOSED
        assert cb.is_available("p1") is True

    def test_success_does_not_affect_closed_state(self) -> None:
        cb = CircuitBreaker(error_threshold=3, cooldown_seconds=10, window_seconds=60)
        cb.record_success("p1")
        assert cb.get_state("p1") == STATE_CLOSED


class TestCircuitBreakerOpen:
    def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(error_threshold=3, cooldown_seconds=10, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")
        cb.record_failure("p1")
        assert cb.get_state("p1") == STATE_OPEN
        assert cb.is_available("p1") is False

    def test_open_rejects_requests(self) -> None:
        cb = CircuitBreaker(error_threshold=2, cooldown_seconds=100, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")
        assert cb.is_available("p1") is False
        assert cb.is_available("p1") is False

    def test_independent_providers(self) -> None:
        cb = CircuitBreaker(error_threshold=2, cooldown_seconds=10, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")
        assert cb.get_state("p1") == STATE_OPEN
        assert cb.get_state("p2") == STATE_CLOSED
        assert cb.is_available("p2") is True


class TestCircuitBreakerHalfOpen:
    def test_transitions_to_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker(error_threshold=2, cooldown_seconds=1, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")
        assert cb.get_state("p1") == STATE_OPEN

        # Simulate cooldown passing
        with patch("src.balancer.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2
            assert cb.get_state("p1") == STATE_HALF_OPEN

    def test_half_open_allows_one_probe(self) -> None:
        cb = CircuitBreaker(error_threshold=2, cooldown_seconds=1, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")

        with patch("src.balancer.circuit_breaker.time") as mock_time:
            future = time.monotonic() + 2
            mock_time.monotonic.return_value = future
            # First call: probe allowed
            assert cb.is_available("p1") is True
            # Second call: probe already in flight
            assert cb.is_available("p1") is False

    def test_half_open_success_closes_circuit(self) -> None:
        cb = CircuitBreaker(error_threshold=2, cooldown_seconds=1, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")

        with patch("src.balancer.circuit_breaker.time") as mock_time:
            future = time.monotonic() + 2
            mock_time.monotonic.return_value = future
            assert cb.is_available("p1") is True  # probe
            cb.record_success("p1")
            assert cb.get_state("p1") == STATE_CLOSED
            assert cb.is_available("p1") is True

    def test_half_open_failure_reopens_circuit(self) -> None:
        cb = CircuitBreaker(error_threshold=2, cooldown_seconds=1, window_seconds=60)
        cb.record_failure("p1")
        cb.record_failure("p1")

        with patch("src.balancer.circuit_breaker.time") as mock_time:
            future = time.monotonic() + 2
            mock_time.monotonic.return_value = future
            assert cb.is_available("p1") is True  # probe
            cb.record_failure("p1")
            assert cb.get_state("p1") == STATE_OPEN


class TestCircuitBreakerSlidingWindow:
    def test_old_failures_expire(self) -> None:
        cb = CircuitBreaker(error_threshold=3, cooldown_seconds=10, window_seconds=5)

        base = time.monotonic()
        with patch("src.balancer.circuit_breaker.time") as mock_time:
            # Two failures at t=0
            mock_time.monotonic.return_value = base
            cb.record_failure("p1")
            cb.record_failure("p1")

            # One failure at t=6 (first two expired from 5s window)
            mock_time.monotonic.return_value = base + 6
            cb.record_failure("p1")

            # Should still be closed: only 1 failure in window
            assert cb.get_state("p1") == STATE_CLOSED

    def test_failures_within_window_accumulate(self) -> None:
        cb = CircuitBreaker(error_threshold=3, cooldown_seconds=10, window_seconds=60)

        for _ in range(3):
            cb.record_failure("p1")

        assert cb.get_state("p1") == STATE_OPEN
