"""In-memory agent registry with thread-safe operations."""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import UTC, datetime

from src.schemas.agent import Agent, AgentCreate


class AgentRegistry:
    """Thread-safe in-memory CRUD for A2A agents."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._lock = asyncio.Lock()

    async def add_agent(self, agent: AgentCreate) -> Agent:
        """Register a new agent, assigning UUID id and generating a token."""
        async with self._lock:
            new_id = uuid.uuid4().hex
            registered = Agent(
                id=new_id,
                name=agent.name,
                description=agent.description,
                methods=list(agent.methods),
                endpoint_url=agent.endpoint_url,
                token=secrets.token_urlsafe(32),
                created_at=datetime.now(UTC),
            )
            self._agents[new_id] = registered
            return registered

    async def get_agent(self, agent_id: str) -> Agent | None:
        """Get agent by id."""
        async with self._lock:
            return self._agents.get(agent_id)

    async def list_agents(self) -> list[Agent]:
        """Return all registered agents."""
        async with self._lock:
            return list(self._agents.values())

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete agent by id. Returns True if found and deleted."""
        async with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                return True
            return False


agent_registry = AgentRegistry()
