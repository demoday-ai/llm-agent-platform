"""Utility Agent - single-turn summarize / translate / analyze."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Literal

from fastapi import FastAPI
from langfuse import Langfuse
from pydantic import BaseModel

from agents.common.platform_client import PlatformClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL = "stepfun/step-3.5-flash"

_TASK_PROMPTS: dict[str, str] = {
    "summarize": "Summarize the following text concisely, preserving key points:\n\n",
    "translate": (
        "Translate the following text to English."
        " If already in English, translate to Russian:\n\n"
    ),
    "analyze": (
        "Analyze the following text. Identify key themes,"
        " sentiment, and provide brief insights:\n\n"
    ),
}

_platform: PlatformClient | None = None
_langfuse: Langfuse | None = None


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
        agent_name="utility-agent",
        agent_description="Utility agent for summarization, translation, and text analysis",
        methods=["run"],
        endpoint_url="http://utility-agent:8003",
    )
    await _platform.register()
    yield
    await _platform.close()


app = FastAPI(title="Utility Agent", lifespan=lifespan)


class RunRequest(BaseModel):
    text: str
    task: Literal["summarize", "translate", "analyze"]


class RunResponse(BaseModel):
    result: str
    task: str


@app.post("/run", response_model=RunResponse)
async def run(body: RunRequest) -> RunResponse:
    assert _platform is not None  # noqa: S101

    prompt = _TASK_PROMPTS[body.task]
    messages = [
        {"role": "system", "content": "You are a helpful utility assistant."},
        {"role": "user", "content": prompt + body.text},
    ]

    trace = None
    if _langfuse is not None:
        trace = _langfuse.trace(
            name="utility-agent-run",
            input={"text": body.text, "task": body.task},
        )

    result: dict[str, Any] = await _platform.chat(
        messages=messages,
        model=MODEL,
    )

    content = result["choices"][0]["message"]["content"]

    if trace is not None:
        trace.update(output={"result": content})

    return RunResponse(result=content, task=body.task)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
