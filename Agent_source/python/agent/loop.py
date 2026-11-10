"""The agent loop:
call the model -> run the tool calls it asks for -> append the results -> repeat,
until the model answers without tool calls or the step budget runs out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TextIO

from agent.llm import ROLE_SYSTEM, ROLE_TOOL, ROLE_USER, ChatModel, ChatRequest, Message, Usage
from agent.tools import Registry


@dataclass
class Result:
    # The model's last answer (the message without tool calls).
    final: str = ""
    # The full conversation, including the system prompt.
    messages: list[Message] = field(default_factory=list)
    steps: int = 0
    usage: Usage = field(default_factory=Usage)


class AgentError(Exception):
    """Raised when a run fails; carries the partial result."""

    def __init__(self, message: str, result: Result):
        super().__init__(message)
        self.result = result


class MaxStepsError(AgentError):
    pass


@dataclass
class Agent:
    model: ChatModel
    model_name: str
    tools: Registry
    system_prompt: str = ""
    max_steps: int = 30  # model calls per run
    log: TextIO | None = None  # progress output; None means silent

    def run(self, task: str) -> Result:
        res = Result()
        if self.system_prompt:
            res.messages.append(Message(role=ROLE_SYSTEM, content=self.system_prompt))
        res.messages.append(Message(role=ROLE_USER, content=task))

        for step in range(1, self.max_steps + 1):
            res.steps = step
            try:
                resp = self.model.chat(
                    ChatRequest(model=self.model_name, messages=list(res.messages), tools=self.tools.specs())
                )
            except Exception as e:
                raise AgentError(f"step {step}: {e}", res) from e
            res.usage.prompt_tokens += resp.usage.prompt_tokens
            res.usage.completion_tokens += resp.usage.completion_tokens
            res.usage.total_tokens += resp.usage.total_tokens

            msg = resp.message
            res.messages.append(msg)
            if not msg.tool_calls:
                res.final = msg.content
                return res

            # Tool calls run in order: a later call often depends on an earlier one.
            for call in msg.tool_calls:
                self._log(f"[{step}] > {call.function.name} {call.function.arguments}")
                try:
                    output = self.tools.call(call.function.name, call.function.arguments)
                except Exception as e:
                    output = f"Error: {e}"
                self._log(f"    {_preview(output, 200)}")
                res.messages.append(Message(role=ROLE_TOOL, tool_call_id=call.id, content=output))

        raise MaxStepsError("agent stopped: step limit reached before the task finished", res)

    def _log(self, line: str) -> None:
        if self.log is not None:
            print(line, file=self.log)


def _preview(s: str, n: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + " ..."


def default_system_prompt(workspace_root: str) -> str:
    """Describes the environment and working style to the model."""
    return f"""You are a coding agent working in a local repository at {workspace_root}.
Paths are relative to the workspace root.

How to work:
1. Explore first: list files with the shell tool and read the relevant code and tests.
2. Make the smallest change that solves the task, using edit_file (or write_file for new files).
   Do not modify tests unless the task asks for it.
3. Verify by running the tests with the shell tool. If they fail, read the error and fix it.
4. When you are done, reply with a short summary of what you changed and how you verified it,
   and make no further tool calls."""
