"""Minimal client for OpenAI-compatible Chat Completions APIs
(OpenAI, Moonshot/Kimi, vLLM, SGLang, Ollama, ...).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ToolCall:
        fn = d.get("function") or {}
        return cls(
            id=d.get("id", ""),
            type=d.get("type", "function"),
            function=FunctionCall(name=fn.get("name", ""), arguments=fn.get("arguments") or ""),
        )


@dataclass
class Message:
    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        return cls(
            role=d.get("role", ROLE_ASSISTANT),
            content=d.get("content") or "",
            tool_calls=[ToolCall.from_dict(tc) for tc in d.get("tool_calls") or []],
            tool_call_id=d.get("tool_call_id", ""),
        )


@dataclass
class ChatRequest:
    model: str
    messages: list[Message]
    # OpenAI tool specs: {"type": "function", "function": {name, description, parameters}}
    tools: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"model": self.model, "messages": [m.to_dict() for m in self.messages]}
        if self.tools:
            d["tools"] = self.tools
        return d


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
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, req: ChatRequest) -> ChatResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(req.to_dict()).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise LLMError(f"chat completions: HTTP {e.code}: {body}") from e

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"chat completions: decode response: {e}") from e
        choices = parsed.get("choices") or []
        if not choices:
            raise LLMError("chat completions: response has no choices")

        msg = Message.from_dict(choices[0].get("message") or {})
        msg.role = ROLE_ASSISTANT
        u = parsed.get("usage") or {}
        usage = Usage(
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
            total_tokens=u.get("total_tokens", 0),
        )
        return ChatResponse(message=msg, usage=usage)
