from __future__ import annotations

import os


class Workspace:
    """Confines file tools to a single root directory."""

    def __init__(self, root: str):
        self.root = os.path.realpath(root)
        if not os.path.isdir(self.root):
            raise NotADirectoryError(f"workspace {root} is not a directory")

    def resolve(self, path: str) -> str:
        """Map a path given by the model (relative to the root, or absolute) to a
        real path inside the workspace. Symlinks are resolved, so a link cannot be
        used to escape the root. The path itself does not need to exist yet."""
        if not path or not path.strip():
            raise ValueError("path is empty")
        if not os.path.isabs(path):
            path = os.path.join(self.root, path)
        real = os.path.realpath(path)
        if os.path.commonpath([self.root, real]) != self.root:
            raise PermissionError(f"path {path!r} is outside the workspace {self.root}")
        return real

    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.root)
