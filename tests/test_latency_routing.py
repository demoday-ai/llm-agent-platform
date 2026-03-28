"""Unit tests for latency-based provider selection."""

from __future__ import annotations

from src.balancer.latency_based import LatencyBasedStrategy
from src.providers.models import Provider


def _make_provider(id: str, weight: float = 1.0) -> Provider:
    return Provider(
        id=id,
        name=f"provider-{id}",
        base_url="https://openrouter.ai/api/v1",
        models=["test-model"],
        weight=weight,
    )


class TestLatencyBasedStrategy:
    def test_selects_lowest_latency(self) -> None:
        strategy = LatencyBasedStrategy(alpha=0.3)
        providers = [_make_provider("fast"), _make_provider("slow")]

        strategy.record_latency("fast", 0.1)
        strategy.record_latency("slow", 1.0)

        selected = strategy.select_provider(providers)
        assert selected.id == "fast"

    def test_falls_back_to_round_robin_without_data(self) -> None:
        strategy = LatencyBasedStrategy()
        providers = [_make_provider("a"), _make_provider("b")]

        # No latency data recorded - should use round-robin fallback
        results = [strategy.select_provider(providers).id for _ in range(4)]
        assert results == ["a", "b", "a", "b"]

    def test_partial_data_uses_known_providers(self) -> None:
        strategy = LatencyBasedStrategy()
        providers = [_make_provider("known"), _make_provider("unknown")]

        strategy.record_latency("known", 0.5)
        # "unknown" has no data, but "known" does
        selected = strategy.select_provider(providers)
        assert selected.id == "known"

    def test_ema_formula(self) -> None:
        strategy = LatencyBasedStrategy(alpha=0.3)

        strategy.record_latency("p1", 1.0)
        assert strategy.get_average("p1") == 1.0

        strategy.record_latency("p1", 0.4)
        # EMA: 0.3 * 0.4 + 0.7 * 1.0 = 0.12 + 0.70 = 0.82
        avg = strategy.get_average("p1")
        assert avg is not None
        assert abs(avg - 0.82) < 1e-9

        strategy.record_latency("p1", 0.4)
        # EMA: 0.3 * 0.4 + 0.7 * 0.82 = 0.12 + 0.574 = 0.694
        avg = strategy.get_average("p1")
        assert avg is not None
        assert abs(avg - 0.694) < 1e-9

    def test_adapts_to_changing_latency(self) -> None:
        strategy = LatencyBasedStrategy(alpha=0.3)
        providers = [_make_provider("a"), _make_provider("b")]

        # Initially a is faster
        strategy.record_latency("a", 0.1)
        strategy.record_latency("b", 1.0)
        assert strategy.select_provider(providers).id == "a"

        # a gets slow, b gets fast (multiple updates to shift EMA)
        for _ in range(20):
            strategy.record_latency("a", 2.0)
            strategy.record_latency("b", 0.05)

        assert strategy.select_provider(providers).id == "b"

    def test_no_data_returns_none_average(self) -> None:
        strategy = LatencyBasedStrategy()
        assert strategy.get_average("nonexistent") is None

    def test_single_provider_always_selected(self) -> None:
        strategy = LatencyBasedStrategy()
        providers = [_make_provider("only")]
        strategy.record_latency("only", 0.5)

        for _ in range(5):
            assert strategy.select_provider(providers).id == "only"


class TestHealthAwareFilter:
    def test_filters_unhealthy(self) -> None:
        from src.balancer.health_aware import filter_healthy

        providers = [
            _make_provider("a").model_copy(update={"health_status": "healthy"}),
            _make_provider("b").model_copy(update={"health_status": "unhealthy"}),
        ]
        result = filter_healthy(providers)
        assert len(result) == 1
        assert result[0].id == "a"

    def test_fallback_to_degraded(self) -> None:
        from src.balancer.health_aware import filter_healthy

        providers = [
            _make_provider("a").model_copy(update={"health_status": "unhealthy"}),
            _make_provider("b").model_copy(update={"health_status": "degraded"}),
        ]
        result = filter_healthy(providers)
        assert len(result) == 1
        assert result[0].id == "b"

    def test_all_unhealthy_returns_all(self) -> None:
        from src.balancer.health_aware import filter_healthy

        providers = [
            _make_provider("a").model_copy(update={"health_status": "unhealthy"}),
            _make_provider("b").model_copy(update={"health_status": "unhealthy"}),
        ]
        result = filter_healthy(providers)
        assert len(result) == 2

    def test_all_healthy_returns_all(self) -> None:
        from src.balancer.health_aware import filter_healthy

        providers = [
            _make_provider("a").model_copy(update={"health_status": "healthy"}),
            _make_provider("b").model_copy(update={"health_status": "healthy"}),
        ]
        result = filter_healthy(providers)
        assert len(result) == 2
