"""Load KEY=VALUE pairs from a .env file into the environment,
so API keys can live in a git-ignored file instead of the shell profile.
"""

from __future__ import annotations

import os
from pathlib import Path


def load() -> Path | None:
    """Find the nearest .env file, starting at the current directory and walking
    up to the git repository root, and set every variable that is not already
    set. Returns the path it loaded, or None if none was found."""
    path = find(Path.cwd())
    if path is not None:
        load_file(path)
    return path


def find(start: Path) -> Path | None:
    for d in (start, *start.parents):
        candidate = d / ".env"
        if candidate.is_file():
            return candidate
        if (d / ".git").exists():
            return None  # stop at the repository root
    return None


def load_file(path: Path) -> None:
    """Set the variables from path. Existing environment variables win."""
    for line in path.read_text().splitlines():
        parsed = parse_line(line)
        if parsed is not None:
            key, value = parsed
            os.environ.setdefault(key, value)


def parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    line = line.removeprefix("export ")
    key, sep, value = line.partition("=")
    key = key.strip()
    if not sep or not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        value = value[1:-1]
    elif " #" in value:
        value = value[: value.index(" #")].strip()
    return key, value
