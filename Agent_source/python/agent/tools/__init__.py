"""Tools the agent can call and the registry that dispatches model tool calls to them."""

from __future__ import annotations

import json
from typing import Any, Protocol

from agent.tools.read_file import ReadFile


class Tool(Protocol):
    name: str
    description: str
    # JSON Schema of the tool's arguments object.
    parameters: dict[str, Any]

    def run(self, args: dict[str, Any]) -> str:
        """Execute the tool. A raised exception is reported back to the model
        as the tool result, so the model can recover from it."""
        ...


class ToolError(Exception):
    pass


class Registry:
    def __init__(self, *tools: Tool):
        # dicts keep insertion order, so specs come out in registration order.
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in self._tools.values()
        ]

    def call(self, name: str, arguments: str) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool {name!r}")
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            raise ToolError(f"arguments for {name} are not valid JSON: {arguments}") from None
        if not isinstance(args, dict):
            raise ToolError(f"arguments for {name} must be a JSON object: {arguments}")
        return tool.run(args)


__all__ = ["ReadFile", "Registry", "Tool", "ToolError"]
