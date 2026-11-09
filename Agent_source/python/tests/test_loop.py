import os
import tempfile
import unittest

from agent.llm import ROLE_ASSISTANT, ChatRequest, ChatResponse, FunctionCall, Message, ToolCall, Usage
from agent.loop import Agent, MaxStepsError
from agent.tools import ReadFile, Registry


class ScriptedModel:
    """Returns canned responses in order and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, req: ChatRequest) -> ChatResponse:
        self.requests.append(req)
        if not self.responses:
            raise RuntimeError("script exhausted")
        msg = self.responses.pop(0)
        msg.role = ROLE_ASSISTANT
        return ChatResponse(message=msg, usage=Usage(total_tokens=10))


def call(id, name, args):
    return ToolCall(id=id, function=FunctionCall(name=name, arguments=args))


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_feeds_tool_results_back(self):
        with open(os.path.join(self.root, "a.txt"), "w") as f:
            f.write("hello")
        model = ScriptedModel([
            Message(role="", tool_calls=[call("c1", "read_file", '{"path":"a.txt"}')]),
            Message(role="", tool_calls=[call("c2", "read_file", '{"path":"missing.txt"}')]),
            Message(role="", content="the file says hello"),
        ])
        agent = Agent(model=model, model_name="m", tools=Registry(ReadFile(self.root)), system_prompt="sys")

        res = agent.run("what is in a.txt?")

        self.assertEqual(res.final, "the file says hello")
        self.assertEqual(res.steps, 3)
        self.assertEqual(res.usage.total_tokens, 30)
        self.assertEqual(
            [m.role for m in res.messages],
            ["system", "user", "assistant", "tool", "assistant", "tool", "assistant"],
        )
        self.assertEqual((res.messages[3].tool_call_id, res.messages[3].content), ("c1", "hello"))
        self.assertEqual(res.messages[5].tool_call_id, "c2")
        self.assertTrue(res.messages[5].content.startswith("Error: "), "tool errors should go back to the model")
        # The second request must carry the first round's tool result.
        self.assertEqual(len(model.requests[1].messages), 4)
        self.assertEqual(len(model.requests[0].tools), 1)
        self.assertEqual(model.requests[0].model, "m")

    def test_run_stops_at_max_steps(self):
        model = ScriptedModel([
            Message(role="", tool_calls=[call("c", "read_file", '{"path":"x"}')]) for _ in range(3)
        ])
        agent = Agent(model=model, model_name="m", tools=Registry(ReadFile(self.root)), max_steps=2)

        with self.assertRaises(MaxStepsError) as ctx:
            agent.run("task")
        self.assertEqual(ctx.exception.result.steps, 2)
        self.assertEqual(len(model.requests), 2)


if __name__ == "__main__":
    unittest.main()
