from __future__ import annotations

import os
from typing import Any

from agent.tools.workspace import Workspace


class WriteFile:
    name = "write_file"
    description = (
        "Create a file, or overwrite an existing one, with the given content. "
        "Parent directories are created. To change part of an existing file, use edit_file instead."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to the workspace root."},
            "content": {"type": "string", "description": "The complete file content."},
        },
        "required": ["path", "content"],
    }

    def __init__(self, ws: Workspace):
        self.ws = ws

    def run(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args.get("path") or "")
        content = args.get("content")
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        if os.path.isdir(path):
            raise IsADirectoryError(f"{self.ws.rel(path)} is a directory")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"wrote {len(content.encode())} bytes to {self.ws.rel(path)}"
