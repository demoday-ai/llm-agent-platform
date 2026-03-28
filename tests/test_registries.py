"""Unit tests for agent registry and provider CRUD API."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.providers.registry import provider_registry
from src.registry.agent_registry import AgentRegistry
from src.schemas.agent import AgentCreate

MASTER_TOKEN = "test-master-token"
AUTH_HEADERS = {"Authorization": f"Bearer {MASTER_TOKEN}"}


# ---------------------------------------------------------------------------
# Agent Registry (unit tests)
# ---------------------------------------------------------------------------


class TestAgentRegistry:
    @pytest.fixture
    def registry(self) -> AgentRegistry:
        return AgentRegistry()

    async def test_add_and_get(self, registry: AgentRegistry) -> None:
        payload = AgentCreate(
            name="echo",
            description="Echo agent",
            methods=["echo"],
            endpoint_url="http://localhost:9000",
        )
        agent = await registry.add_agent(payload)
        assert agent.id != ""
        assert agent.name == "echo"
        assert agent.token != ""
        assert agent.status == "active"

        fetched = await registry.get_agent(agent.id)
        assert fetched is not None
        assert fetched.id == agent.id

    async def test_get_nonexistent_returns_none(self, registry: AgentRegistry) -> None:
        assert await registry.get_agent("does-not-exist") is None

    async def test_list_agents(self, registry: AgentRegistry) -> None:
        await registry.add_agent(
            AgentCreate(name="a", description="", methods=[], endpoint_url="http://a")
        )
        await registry.add_agent(
            AgentCreate(name="b", description="", methods=[], endpoint_url="http://b")
        )
        agents = await registry.list_agents()
        assert len(agents) == 2

    async def test_delete_agent(self, registry: AgentRegistry) -> None:
        agent = await registry.add_agent(
            AgentCreate(name="rm", description="", methods=[], endpoint_url="http://rm")
        )
        assert await registry.delete_agent(agent.id) is True
        assert await registry.get_agent(agent.id) is None
        assert await registry.delete_agent(agent.id) is False

    async def test_token_is_unique(self, registry: AgentRegistry) -> None:
        payload = AgentCreate(
            name="t", description="", methods=[], endpoint_url="http://t"
        )
        a1 = await registry.add_agent(payload)
        a2 = await registry.add_agent(payload)
        assert a1.token != a2.token


# ---------------------------------------------------------------------------
# Agent API (integration via TestClient)
# ---------------------------------------------------------------------------


class TestAgentAPI:
    @pytest.fixture
    async def client(self) -> AsyncClient:
        from src.main import app
        from src.registry.agent_registry import agent_registry

        agent_registry._agents.clear()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        with patch("src.auth.middleware.validate_token") as mock_validate:
            from src.auth.token_store import TokenInfo
            mock_validate.return_value = TokenInfo(
                token=MASTER_TOKEN, agent_id=None, is_master=True,
            )
            yield AsyncClient(
                transport=transport, base_url="http://test", headers=AUTH_HEADERS,
            )

    async def test_register_and_list(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/agents",
            json={
                "name": "echo",
                "description": "Echo",
                "methods": ["echo"],
                "endpoint_url": "http://localhost:9000",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert data["name"] == "echo"

        # list should NOT include token
        resp_list = await client.get("/agents")
        assert resp_list.status_code == 200
        agents = resp_list.json()
        assert len(agents) == 1
        assert "token" not in agents[0]

    async def test_get_agent_no_token(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/agents",
            json={
                "name": "x",
                "description": "X",
                "methods": [],
                "endpoint_url": "http://x",
            },
        )
        agent_id = resp.json()["id"]

        resp_get = await client.get(f"/agents/{agent_id}")
        assert resp_get.status_code == 200
        assert "token" not in resp_get.json()

    async def test_get_nonexistent_agent_404(self, client: AsyncClient) -> None:
        resp = await client.get("/agents/nonexistent")
        assert resp.status_code == 404

    async def test_delete_agent(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/agents",
            json={
                "name": "del",
                "description": "",
                "methods": [],
                "endpoint_url": "http://del",
            },
        )
        agent_id = resp.json()["id"]

        resp_del = await client.delete(f"/agents/{agent_id}")
        assert resp_del.status_code == 204

        resp_get = await client.get(f"/agents/{agent_id}")
        assert resp_get.status_code == 404

    async def test_delete_nonexistent_agent_404(self, client: AsyncClient) -> None:
        resp = await client.delete("/agents/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Provider API (integration via TestClient)
# ---------------------------------------------------------------------------


class TestProviderAPI:
    @pytest.fixture
    async def client(self) -> AsyncClient:
        from src.main import app

        provider_registry._providers.clear()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        with patch("src.auth.middleware.validate_token") as mock_validate:
            from src.auth.token_store import TokenInfo
            mock_validate.return_value = TokenInfo(
                token=MASTER_TOKEN, agent_id=None, is_master=True,
            )
            yield AsyncClient(
                transport=transport, base_url="http://test", headers=AUTH_HEADERS,
            )

    async def test_register_and_list(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/providers",
            json={
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "models": ["gpt-4"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "openrouter"
        assert data["id"] != ""

        resp_list = await client.get("/providers")
        assert resp_list.status_code == 200
        assert len(resp_list.json()) == 1

    async def test_get_provider(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/providers",
            json={
                "name": "p",
                "base_url": "https://x.com",
                "models": ["m"],
            },
        )
        pid = resp.json()["id"]

        resp_get = await client.get(f"/providers/{pid}")
        assert resp_get.status_code == 200
        assert resp_get.json()["name"] == "p"

    async def test_get_nonexistent_provider_404(self, client: AsyncClient) -> None:
        resp = await client.get("/providers/nonexistent")
        assert resp.status_code == 404

    async def test_update_provider(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/providers",
            json={
                "name": "orig",
                "base_url": "https://x.com",
                "models": ["m"],
            },
        )
        pid = resp.json()["id"]

        resp_put = await client.put(
            f"/providers/{pid}",
            json={"name": "updated", "weight": 5.0},
        )
        assert resp_put.status_code == 200
        data = resp_put.json()
        assert data["name"] == "updated"
        assert data["weight"] == 5.0
        # unchanged fields preserved
        assert data["base_url"] == "https://x.com"

    async def test_update_nonexistent_provider_404(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/providers/nonexistent",
            json={"name": "x"},
        )
        assert resp.status_code == 404

    async def test_delete_provider(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/providers",
            json={
                "name": "del",
                "base_url": "https://x.com",
                "models": ["m"],
            },
        )
        pid = resp.json()["id"]

        resp_del = await client.delete(f"/providers/{pid}")
        assert resp_del.status_code == 204

        resp_get = await client.get(f"/providers/{pid}")
        assert resp_get.status_code == 404

    async def test_delete_nonexistent_provider_404(self, client: AsyncClient) -> None:
        resp = await client.delete("/providers/nonexistent")
        assert resp.status_code == 404
