from __future__ import annotations

import os
import shutil
import signal
import subprocess
from typing import Any, Callable

from agent.tools.workspace import Workspace

MAX_OUTPUT = 16 * 1024  # characters returned to the model
MAX_TIMEOUT = 600


class Shell:
    name = "shell"
    description = (
        "Run a shell command (bash -c) in the workspace root and return its exit code and combined "
        "stdout/stderr. Use it to explore the project and run tests. Use edit_file / write_file to change files."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to run."},
            "timeout_sec": {"type": "integer", "description": "Optional timeout in seconds (default 120, max 600)."},
        },
        "required": ["command"],
    }

    def __init__(
        self,
        ws: Workspace,
        timeout: int = 120,
        approve: Callable[[str], bool] | None = None,
        env: dict[str, str] | None = None,
    ):
        """approve is asked before every command; None runs everything, so only
        use None on a throwaway copy of the code. env is merged into the
        inherited environment."""
        self.ws = ws
        self.timeout = timeout
        self.approve = approve
        self.env = {**os.environ, **(env or {})}

    def run(self, args: dict[str, Any]) -> str:
        command = args.get("command") or ""
        if not command.strip():
            raise ValueError("command is empty")
        if self.approve is not None and not self.approve(command):
            raise PermissionError("command was not approved by the user; try a different approach")
        timeout = min(int(args.get("timeout_sec") or self.timeout), MAX_TIMEOUT)

        shell = shutil.which("bash") or "sh"
        # A new session lets a timeout kill the whole process tree, not just bash.
        proc = subprocess.Popen(
            [shell, "-c", command],
            cwd=self.ws.root,
            env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            out, _ = proc.communicate(timeout=timeout)
            status = str(proc.returncode)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
            status = f"timeout (killed after {timeout}s)"
        return f"exit_code: {status}\n{_truncate_middle(out.decode(errors='replace'), MAX_OUTPUT)}"


def _truncate_middle(s: str, limit: int) -> str:
    """Keep the head and tail, where compiler errors and test summaries usually are."""
    if len(s) <= limit:
        return s
    half = limit // 2
    return f"{s[:half]}\n\n... [{len(s) - limit} characters truncated] ...\n\n{s[-half:]}"
