from __future__ import annotations

import os
from typing import Any

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

    def __init__(self, root: str):
        # The workspace directory relative paths are resolved against.
        # It does not stop absolute paths or "../" yet; confinement comes with
        # the write and shell tools.
        self.root = root

    def run(self, args: dict[str, Any]) -> str:
        path = args.get("path") or ""
        if not path:
            raise ValueError("path is empty")
        if not os.path.isabs(path):
            path = os.path.join(self.root, path)
        with open(path, "rb") as f:
            data = f.read()
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        if len(data) > MAX_READ_BYTES:
            return text + f"\n... [truncated: file is {len(data)} bytes]"
        return text
