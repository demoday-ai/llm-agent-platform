"""Tests for POST /v1/embeddings endpoint."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.schemas.openai import EmbeddingRequest


class TestEmbeddingRequest:
    """Test EmbeddingRequest schema validation."""

    def test_valid_string_input(self):
        req = EmbeddingRequest(model="google/gemini-embedding-001", input="hello")
        assert req.model == "google/gemini-embedding-001"
        assert req.input == "hello"

    def test_valid_list_input(self):
        req = EmbeddingRequest(model="test-model", input=["hello", "world"])
        assert isinstance(req.input, list)
        assert len(req.input) == 2

    def test_extra_fields_allowed(self):
        req = EmbeddingRequest(model="test", input="text", dimensions=3072)
        assert req.model == "test"


class TestEmbeddingEndpoint:
    """Test /v1/embeddings endpoint."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("MASTER_TOKEN", "test-master-token")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    @pytest.fixture
    def client(self, mock_env):
        from fastapi.testclient import TestClient
        from src.main import app
        return TestClient(app)

    def test_embedding_requires_auth(self, client):
        resp = client.post("/v1/embeddings", json={"model": "test", "input": "hello"})
        assert resp.status_code == 401

    def test_embedding_agent_token_allowed(self, client):
        """Agent tokens should be allowed to access /v1/embeddings."""
        from src.auth.middleware import AGENT_ALLOWED_PREFIXES
        assert "/v1/embeddings" in AGENT_ALLOWED_PREFIXES

    def test_embedding_schema_in_openai(self):
        """EmbeddingRequest should be importable from openai schemas."""
        from src.schemas.openai import EmbeddingRequest
        assert EmbeddingRequest is not None

    def test_embedding_metrics_defined(self):
        """Embedding metrics should be defined."""
        from src.telemetry.metrics import (
            llm_embedding_requests_total,
            llm_embedding_duration_seconds,
        )
        assert llm_embedding_requests_total is not None
        assert llm_embedding_duration_seconds is not None

    def test_embedding_router_registered(self, client):
        """Embeddings endpoint should be registered."""
        routes = [r.path for r in client.app.routes]
        assert "/v1/embeddings" in routes
