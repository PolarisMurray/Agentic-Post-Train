from __future__ import annotations

import os
from typing import Any

from agent.tools.workspace import Workspace

MAX_READ_BYTES = 64 * 1024


class ReadFile:
    name = "read_file"
    description = "Read a text file and return its content. Paths are relative to the workspace root."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to the workspace root."},
        },
        "required": ["path"],
    }

    def __init__(self, ws: Workspace):
        self.ws = ws

    def run(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args.get("path") or "")
        if os.path.isdir(path):
            raise IsADirectoryError(f"{self.ws.rel(path)} is a directory; use the shell tool (ls) to list it")
        with open(path, "rb") as f:
            data = f.read(MAX_READ_BYTES + 1)
        if b"\0" in data:
            raise ValueError(f"{self.ws.rel(path)} looks like a binary file")
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        if len(data) > MAX_READ_BYTES:
            return text + f"\n... [truncated: file is {os.path.getsize(path)} bytes]"
        return text
