"""Prometheus metrics definitions.

Metrics are *defined* here and *recorded* by other modules
(completions endpoint, balancer, etc.).
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ── Counters ────────────────────────────────────────────────

llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["model", "provider", "status_code"],
)

llm_tokens_input_total = Counter(
    "llm_tokens_input_total",
    "Total input tokens",
    ["model"],
)

llm_tokens_output_total = Counter(
    "llm_tokens_output_total",
    "Total output tokens",
    ["model"],
)

llm_request_cost_total = Counter(
    "llm_request_cost_total",
    "Total request cost in USD",
    ["model", "provider"],
)

# ── Histograms ──────────────────────────────────────────────

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds (end-to-end)",
    ["model", "provider"],
)

llm_overhead_duration_seconds = Histogram(
    "llm_overhead_duration_seconds",
    "Platform overhead only (excluding upstream LLM latency)",
    ["model"],
)

llm_ttft_seconds = Histogram(
    "llm_ttft_seconds",
    "Time to first token",
    ["model", "provider"],
)

llm_tpot_seconds = Histogram(
    "llm_tpot_seconds",
    "Time per output token",
    ["model", "provider"],
)
