from __future__ import annotations

from typing import Any

from agent.tools.workspace import Workspace


class EditFile:
    """Exact string replacement, in the style of OpenHands' str_replace editor."""

    name = "edit_file"
    description = (
        "Edit a file by replacing one exact occurrence of old_str with new_str. "
        "old_str must match the file exactly (including indentation) and appear exactly once; "
        "include a few surrounding lines to make it unique. Read the file first."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to the workspace root."},
            "old_str": {"type": "string", "description": "The exact text to replace."},
            "new_str": {"type": "string", "description": "The replacement text."},
        },
        "required": ["path", "old_str", "new_str"],
    }

    def __init__(self, ws: Workspace):
        self.ws = ws

    def run(self, args: dict[str, Any]) -> str:
        path = self.ws.resolve(args.get("path") or "")
        old, new = args.get("old_str"), args.get("new_str")
        if not isinstance(old, str) or not old:
            raise ValueError("old_str must be a non-empty string")
        if not isinstance(new, str):
            raise ValueError("new_str must be a string")
        with open(path, encoding="utf-8") as f:
            text = f.read()

        count = text.count(old)
        rel = self.ws.rel(path)
        if count == 0:
            raise ValueError(f"old_str not found in {rel}; read the file and copy the text exactly")
        if count > 1:
            raise ValueError(f"old_str appears {count} times in {rel}; include more context to make it unique")

        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new, 1))
        line = text[: text.index(old)].count("\n") + 1
        return f"edited {rel} at line {line}"
