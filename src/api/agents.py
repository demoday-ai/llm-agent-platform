"""CRUD HTTP API for A2A agent registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.registry.agent_registry import agent_registry
from src.schemas.agent import Agent, AgentCreate, AgentPublic

router = APIRouter(prefix="/agents", tags=["agents"])


def _to_public(agent: Agent) -> AgentPublic:
    return AgentPublic(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        methods=agent.methods,
        endpoint_url=agent.endpoint_url,
        status=agent.status,
        created_at=agent.created_at,
    )


@router.post("", response_model=Agent, status_code=201)
async def register_agent(body: AgentCreate) -> Agent:
    """Register a new agent. Returns the full Agent including token."""
    return await agent_registry.add_agent(body)


@router.get("", response_model=list[AgentPublic])
async def list_agents() -> list[AgentPublic]:
    """List all registered agents (tokens excluded)."""
    agents = await agent_registry.list_agents()
    return [_to_public(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentPublic)
async def get_agent(agent_id: str) -> AgentPublic:
    """Get a single agent card (token excluded)."""
    agent = await agent_registry.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_public(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str) -> None:
    """Delete an agent by id."""
    deleted = await agent_registry.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
