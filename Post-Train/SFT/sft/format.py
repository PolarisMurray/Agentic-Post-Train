"""How a trajectory is rendered into text for the student model.

The layout follows the design of the Kimi K3 chat template (XTML: XML-like markup
whose structural boundaries are special tokens). Training and (later) inference
must use exactly the same format, so it lives here.

    [open]message role="system" type="tool-declare"[sep]{tool specs}[close]message[sep]
    [open]message role="system"[sep]{system prompt}[close]message[sep]
    [open]message role="user"[sep]{task}[close]message[sep]
    [open]message role="assistant"[sep][open]think[sep]{reasoning}[close]think[sep]
      [open]response[sep]{answer}[close]response[sep]
      [open]tools[sep][open]call tool="edit_file" index="0"[sep]
        [open]arg name="path"[sep]a.py[close]arg[sep]
        [open]arg name="timeout_sec" type="json"[sep]30[close]arg[sep]
      [close]call[sep][close]tools[sep][close]message[sep][end_of_msg]
    [open]message role="tool" tool="edit_file" index="0"[sep]{output}[close]message[sep]

Only what the model generates is trained on: everything in an assistant message
after the generation prefix ([open]message role="assistant"[sep][open]think[sep]),
through [end_of_msg].
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

Segment = tuple[str, bool]  # (text, trainable)


@dataclass
class ChatFormat:
    # Existing BOS token of the student (DeepSeek-R1-Distill-Qwen).
    bos: str = "<｜begin▁of▁sentence｜>"

    # XTML structure tokens. They are NOT in the student's vocabulary: training
    # must add them as special tokens and train their embeddings.
    open: str = "<|open|>"
    sep: str = "<|sep|>"
    close: str = "<|close|>"
    end_of_msg: str = "<|end_of_msg|>"  # generation stop marker
    # True: thinking mode (think channel kept in every assistant message).
    # False: instruct mode (only response and tools channels).
    include_reasoning: bool = True
    # Optional global option, stated in natural language: low / medium / high / max.
    reasoning_effort: str | None = None

    def special_tokens(self) -> list[str]:
        """Tokens that must be added to the tokenizer before training."""
        return [self.open, self.sep, self.close, self.end_of_msg]


def open_tag(fmt: ChatFormat, tag: str, **attrs: Any) -> str:

    attr_text = ""
    for k, v in attrs.items():
        safe_value = str(v).replace('"', "&quot;")
        one_attr = f' {k} = “{safe_value}” '

        attr_text += one_attr
    result = f'{fmt.open}{tag}{attr_text}{fmt.sep}'

    return result


def close_tag(fmt: ChatFormat, tag: str) -> str:
    return f"{fmt.close}{tag}{fmt.sep}"


def element(fmt: ChatFormat, tag: str, body: str, **attrs: Any) -> str:
    return open_tag(fmt, tag, **attrs) + body + close_tag(fmt, tag)


def render_arguments(fmt: ChatFormat, arguments: str) -> Segment:
    """Typed argument blocks: strings stay raw text (code is not JSON-escaped),
    other JSON values are compactly serialized. Arguments that are not a JSON
    object fall back to a pure-JSON block, which is never trained on."""
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        args = None
    if not isinstance(args, dict):
        return element(fmt, "json", arguments), False
    parts = []
    for name, value in args.items():
        if isinstance(value, str):
            parts.append(element(fmt, "arg", value, name=name))
        else:
            compact = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            parts.append(element(fmt, "arg", compact, name=name, type="json"))
    return "".join(parts), True


def render_assistant(fmt: ChatFormat, msg: dict[str, Any]) -> list[Segment]:
    """An assistant message: the generation prefix (not trained), then channels."""
    first = "think" if fmt.include_reasoning else "response"
    segments: list[Segment] = [(open_tag(fmt, "message", role="assistant") + open_tag(fmt, first), False)]

    body = ""
    if fmt.include_reasoning:
        # Preserved thinking: the think channel is always present, even if empty.
        body += (msg.get("reasoning_content") or "") + close_tag(fmt, "think")
        if msg.get("content"):
            body += element(fmt, "response", msg["content"])
    else:
        body += (msg.get("content") or "") + close_tag(fmt, "response")

    calls = msg.get("tool_calls") or []
    if calls:
        body += open_tag(fmt, "tools")
        for index, call in enumerate(calls):
            body += open_tag(fmt, "call", tool=call["function"]["name"], index=index)
            args_text, trainable = render_arguments(fmt, call["function"]["arguments"])
            if trainable:
                body += args_text
            else:
                segments += [(body, True), (args_text, False)]
                body = ""
            body += close_tag(fmt, "call")
        body += close_tag(fmt, "tools")
    body += close_tag(fmt, "message") + fmt.end_of_msg
    segments.append((body, True))
    return segments


def render(messages: list[dict[str, Any]], tools: list[dict[str, Any]], fmt: ChatFormat) -> list[Segment]:
    """Render a conversation into segments; trainable segments are what the model generates."""
    segments: list[Segment] = [(fmt.bos, False)]

    # Global options come before all input messages.
    if tools:
        specs = "\n".join(json.dumps(t["function"], ensure_ascii=False) for t in tools)
        segments.append((element(fmt, "message", specs, role="system", type="tool-declare"), False))
    if fmt.include_reasoning and fmt.reasoning_effort:
        text = f"Reasoning effort: {fmt.reasoning_effort}."
        segments.append((element(fmt, "message", text, role="system", type="thinking-effort"), False))

    # Each tool result repeats the tool/index pair of the call it answers.
    call_ids: dict[str, tuple[str, int]] = {}
    for msg in messages:
        role = msg["role"]
        if role in ("system", "user"):
            segments.append((element(fmt, "message", msg["content"], role=role), False))
        elif role == "assistant":
            segments += render_assistant(fmt, msg)
            for index, call in enumerate(msg.get("tool_calls") or []):
                call_ids[call["id"]] = (call["function"]["name"], index)
        elif role == "tool":
            name, index = call_ids.get(msg.get("tool_call_id", ""), ("unknown", 0))
            segments.append((element(fmt, "message", msg["content"], role="tool", tool=name, index=index), False))
        else:
            raise ValueError(f"unexpected role {role!r}")
    return segments


def to_text(segments: list[Segment]) -> str:
    return "".join(text for text, _ in segments)
