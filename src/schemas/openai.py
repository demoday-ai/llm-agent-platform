"""Pydantic models for OpenAI-compatible chat completion API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Message(BaseModel):
    model_config = {"extra": "allow"}

    role: str
    content: str | None = None


class EmbeddingRequest(BaseModel):
    model_config = {"extra": "allow"}

    model: str
    input: str | list[str]


class ChatCompletionRequest(BaseModel):
    model_config = {"extra": "allow"}

    model: str
    messages: list[Message]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: str | list[str] | None = None
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = Field(default="chat.completion")
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
