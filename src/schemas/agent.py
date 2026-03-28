"""Pydantic models for A2A agent registry."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - required at runtime by Pydantic

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    description: str
    methods: list[str]
    endpoint_url: str


class Agent(BaseModel):
    id: str
    name: str
    description: str
    methods: list[str]
    endpoint_url: str
    token: str
    status: str = "active"
    created_at: datetime


class AgentPublic(BaseModel):
    """Agent representation without the secret token."""

    id: str
    name: str
    description: str
    methods: list[str]
    endpoint_url: str
    status: str
    created_at: datetime
