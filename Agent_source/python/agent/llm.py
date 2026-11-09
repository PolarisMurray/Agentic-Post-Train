"""Chat Completions client built on the OpenAI SDK, for any OpenAI-compatible API
(DeepSeek, OpenAI, Moonshot/Kimi, vLLM, SGLang, Ollama, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import openai

ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"


@dataclass
class FunctionCall:
    name: str
    # A JSON object encoded as a string, as returned by the API.
    arguments: str


@dataclass
class ToolCall:
    id: str
    function: FunctionCall
    type: str = "function"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""
    # Returned by thinking models (e.g. DeepSeek in thinking mode). DeepSeek
    # rejects requests with tools (HTTP 400) unless it is sent back unchanged.
    reasoning_content: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.reasoning_content:
            d["reasoning_content"] = self.reasoning_content
        return d


@dataclass
class ChatRequest:
    model: str
    messages: list[Message]
    # OpenAI tool specs: {"type": "function", "function": {name, description, parameters}}
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    message: Message
    usage: Usage


class ChatModel(Protocol):
    """What the agent loop depends on, so tests can swap in a fake."""

    def chat(self, req: ChatRequest) -> ChatResponse: ...


class LLMError(Exception):
    pass


class Client:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 300):
        # The SDK retries connection errors, 429 and 5xx with backoff.
        self._client = openai.OpenAI(base_url=base_url, api_key=api_key or None, timeout=timeout, max_retries=2)

    def chat(self, req: ChatRequest) -> ChatResponse:
        kwargs: dict[str, Any] = {"model": req.model, "messages": [m.to_dict() for m in req.messages]}
        if req.tools:
            kwargs["tools"] = req.tools
        try:
            completion = self._client.chat.completions.create(**kwargs)
        except openai.APIError as e:
            raise LLMError(f"chat completions: {e}") from e
        if not completion.choices:
            raise LLMError("chat completions: response has no choices")

        out = completion.choices[0].message
        msg = Message(
            role=ROLE_ASSISTANT,
            content=out.content or "",
            # Not part of the OpenAI schema; the SDK keeps unknown fields as attributes.
            reasoning_content=getattr(out, "reasoning_content", None) or "",
            tool_calls=[
                ToolCall(id=tc.id, function=FunctionCall(name=tc.function.name, arguments=tc.function.arguments))
                for tc in out.tool_calls or []
                if tc.type == "function"
            ],
        )
        u = completion.usage
        usage = Usage(
            prompt_tokens=u.prompt_tokens if u else 0,
            completion_tokens=u.completion_tokens if u else 0,
            total_tokens=u.total_tokens if u else 0,
        )
        return ChatResponse(message=msg, usage=usage)
