"""DemoDay Curator Agent - answers with local tool use."""

from __future__ import annotations

import json
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

MODEL = "deepseek/deepseek-chat"

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "compare",
            "description": "Compare a list of items and produce a comparison table",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Items to compare",
                    },
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize",
            "description": "Summarize the given text",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to summarize"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_questions",
            "description": "Suggest questions about a topic for deeper exploration",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to explore"},
                },
                "required": ["topic"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a Demo Day curator agent. You help guests explore and compare projects. "
    "You have access to tools: compare (compare items), summarize (summarize text), "
    "suggest_questions (suggest exploration questions for a topic). "
    "Use these tools when appropriate to provide structured answers."
)


# --- Local tool implementations (deterministic, no LLM) ---

def _tool_compare(items: list[str]) -> str:
    header = "| Item | Description |"
    separator = "|------|-------------|"
    rows = [f"| {item} | A popular technology/concept |" for item in items]
    table = "\n".join([header, separator, *rows])
    return (
        f"Comparison table for: {', '.join(items)}\n{table}\n"
        "Use this table as a basis for your detailed comparison."
    )


def _tool_summarize(text: str) -> str:
    sentences = text.replace("\n", " ").split(". ")
    if len(sentences) <= 3:
        return text
    return ". ".join(sentences[:3]) + "."


def _tool_suggest_questions(topic: str) -> list[str]:
    return [
        f"What problem does {topic} solve?",
        f"How does {topic} compare to alternatives?",
        f"What is the target audience for {topic}?",
        f"What are the key technical decisions behind {topic}?",
        f"What's the roadmap for {topic}?",
    ]


_TOOL_HANDLERS: dict[str, Any] = {
    "compare": lambda args: _tool_compare(args["items"]),
    "summarize": lambda args: _tool_summarize(args["text"]),
    "suggest_questions": lambda args: _tool_suggest_questions(args["topic"]),
}

_platform: PlatformClient | None = None
_langfuse: Langfuse | None = None
_sessions: dict[str, list[dict[str, Any]]] = {}

_MAX_TOOL_ROUNDS = 5


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
        agent_name="curator-agent",
        agent_description=(
            "DemoDay curator agent with tool use"
            " (compare, summarize, suggest_questions)"
        ),
        methods=["run"],
        endpoint_url="http://curator-agent:8002",
    )
    await _platform.register()
    yield
    await _platform.close()


app = FastAPI(title="Curator Agent", lifespan=lifespan)


class RunRequest(BaseModel):
    message: str
    session_id: str | None = None


class RunResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list[str]


def _execute_tool(name: str, arguments: dict[str, Any]) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    result = handler(arguments)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


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
            name="curator-agent-run",
            session_id=session_id,
            input={"message": body.message},
        )

    tools_used: list[str] = []

    for _round in range(_MAX_TOOL_ROUNDS):
        result: dict[str, Any] = await _platform.chat(
            messages=_sessions[session_id],
            model=MODEL,
            tools=TOOLS_SPEC,
        )

        choice = result["choices"][0]
        message = choice["message"]

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            content = message.get("content") or ""
            # If content is empty after tool use, ask LLM to summarize
            if not content.strip() and tools_used:
                _sessions[session_id].append(
                    {
                        "role": "user",
                        "content": "Please summarize based on the tool results.",
                    },
                )
                continue
            _sessions[session_id].append({"role": "assistant", "content": content})

            if trace is not None:
                trace.update(output={"response": content, "tools_used": tools_used})

            return RunResponse(
                response=content,
                session_id=session_id,
                tools_used=tools_used,
            )

        _sessions[session_id].append(message)

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])
            tools_used.append(fn_name)

            if trace is not None:
                span = trace.span(name=f"tool:{fn_name}", input=fn_args)

            tool_result = _execute_tool(fn_name, fn_args)

            if trace is not None:
                span.update(output={"result": tool_result})

            _sessions[session_id].append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })

    content = "Max tool rounds reached."
    if trace is not None:
        trace.update(output={"response": content, "tools_used": tools_used})

    return RunResponse(
        response=content,
        session_id=session_id,
        tools_used=tools_used,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
