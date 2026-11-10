"""Run a minimal coding agent against an OpenAI-compatible model.

    export OPENAI_API_KEY=...
    python -m agent --model gpt-4.1 --workdir ./myproject "what does this project do?"
"""

from __future__ import annotations

import argparse
import os
import sys

from agent import dotenv
from agent.llm import Client
from agent.loop import Agent, AgentError, default_system_prompt
from agent.tools import Workspace, default_tools


def main(argv: list[str] | None = None) -> int:
    # Must run before the arguments below read their defaults from the environment.
    dotenv.load()

    parser = argparse.ArgumentParser(
        prog="agent",
        description="The API key is read from OPENAI_API_KEY (shell or the repo's .env file).",
    )
    parser.add_argument("task", nargs="+", help="what the agent should do")
    parser.add_argument("--workdir", default=".", help="workspace root")
    parser.add_argument("--model", default=os.environ.get("AGENT_MODEL", ""), help="model name (env AGENT_MODEL)")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1",
        help="OpenAI-compatible API base URL (env OPENAI_BASE_URL)",
    )
    parser.add_argument("--max-steps", type=int, default=30, help="maximum number of model calls")
    parser.add_argument(
        "--approval",
        choices=["ask", "auto"],
        default="ask",
        help="ask before every shell command (default), or run them without asking (throwaway copies only)",
    )
    args = parser.parse_args(argv)

    task = " ".join(args.task).strip()
    if not args.model:
        print("error: no model given; pass --model or set AGENT_MODEL", file=sys.stderr)
        return 1
    ws = Workspace(args.workdir)
    approve = None if args.approval == "auto" else _ask_on_terminal

    agent = Agent(
        model=Client(args.base_url, os.environ.get("OPENAI_API_KEY", "")),
        model_name=args.model,
        tools=default_tools(ws, approve=approve),
        system_prompt=default_system_prompt(ws.root),
        max_steps=args.max_steps,
        log=sys.stderr,
    )

    try:
        res = agent.run(task)
    except AgentError as e:
        print(f"[done] steps={e.result.steps} tokens={e.result.usage.total_tokens}", file=sys.stderr)
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    print(f"[done] steps={res.steps} tokens={res.usage.total_tokens}", file=sys.stderr)
    print(res.final)
    return 0


def _ask_on_terminal(command: str) -> bool:
    print(f"\n  approve shell command?\n    $ {command}\n  [y/N] ", end="", file=sys.stderr, flush=True)
    answer = sys.stdin.readline()
    if not answer:
        print("(no input, denied)", file=sys.stderr)
    return answer.strip().lower() in ("y", "yes")


if __name__ == "__main__":
    sys.exit(main())
