"""DemoDay Profile Agent - understands guest interests and goals."""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from langfuse import Langfuse
from pydantic import BaseModel

from agents.common.platform_client import PlatformClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Demo Day profiling agent. Your job is to understand the guest's "
    "interests and goals in 1-2 questions. Extract interests, goals, and create "
    'a structured profile. Respond in JSON format: {"action": "reply"|"profile", '
    '"message": str?, "interests": list[str]?, "goals": list[str]?}'
)

MODEL = "deepseek/deepseek-chat"

_platform: PlatformClient | None = None
_langfuse: Langfuse | None = None
_sessions: dict[str, list[dict[str, str]]] = {}


def _init_langfuse() -> Langfuse | None:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    if not public_key:
        return None
    try:
        return Langfuse(
            public_key=public_key,
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            host=os.getenv("LANGFUSE_HOST", "http://langfuse:3000"),
        )
    except Exception:
        logger.warning("Failed to init Langfuse", exc_info=True)
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _platform, _langfuse  # noqa: PLW0603

    _langfuse = _init_langfuse()

    _platform = PlatformClient(
        platform_url=os.getenv("PLATFORM_URL", "http://app:8000"),
        master_token=os.getenv("MASTER_TOKEN", ""),
        agent_name="profile-agent",
        agent_description="DemoDay profiling agent - extracts guest interests and goals",
        methods=["run"],
        endpoint_url="http://profile-agent:8001",
    )
    await _platform.register()
    yield
    await _platform.close()


app = FastAPI(title="Profile Agent", lifespan=lifespan)


class RunRequest(BaseModel):
    message: str
    session_id: str | None = None


class RunResponse(BaseModel):
    response: str
    session_id: str


@app.post("/run", response_model=RunResponse)
async def run(body: RunRequest) -> RunResponse:
    assert _platform is not None  # noqa: S101

    session_id = body.session_id or str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    _sessions[session_id].append({"role": "user", "content": body.message})

    trace = None
    if _langfuse is not None:
        trace = _langfuse.trace(
            name="profile-agent-run",
            session_id=session_id,
            input={"message": body.message},
        )

    result: dict[str, Any] = await _platform.chat(
        messages=_sessions[session_id],
        model=MODEL,
    )

    content = result["choices"][0]["message"]["content"]
    _sessions[session_id].append({"role": "assistant", "content": content})

    if trace is not None:
        trace.update(output={"response": content})

    return RunResponse(response=content, session_id=session_id)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
