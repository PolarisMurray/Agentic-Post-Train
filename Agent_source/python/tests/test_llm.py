import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent.llm import Client, LLMError
from agent.loop import Agent
from agent.tools import ReadFile, Registry

REASONING = "I should read a.txt first."


class FakeDeepSeek(BaseHTTPRequestHandler):
    """Plays a thinking model and enforces DeepSeek's rule: with tools in the
    request, every earlier assistant reasoning_content must be sent back."""

    requests = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeDeepSeek.requests.append(req)
        assistants = [m for m in req["messages"] if m["role"] == "assistant"]
        if req.get("tools") and any(m.get("reasoning_content") != REASONING for m in assistants):
            return self._send(400, {"error": {"message": "reasoning_content must be passed back"}})

        if not assistants:
            message = {
                "role": "assistant",
                "content": "",
                "reasoning_content": REASONING,
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'}}
                ],
            }
        else:
            message = {"role": "assistant", "content": "a.txt says hello", "reasoning_content": "done"}
        self._send(200, {
            "id": "x", "object": "chat.completion", "created": 0, "model": req["model"],
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ClientTest(unittest.TestCase):
    def setUp(self):
        FakeDeepSeek.requests = []
        self.server = HTTPServer(("127.0.0.1", 0), FakeDeepSeek)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_reasoning_content_round_trip(self):
        with open(os.path.join(self.tmp.name, "a.txt"), "w") as f:
            f.write("hello")
        agent = Agent(
            model=Client(self.base_url, "sk-test"),
            model_name="deepseek-flash",
            tools=Registry(ReadFile(self.tmp.name)),
        )

        res = agent.run("what is in a.txt?")

        self.assertEqual(res.final, "a.txt says hello")
        self.assertEqual(res.usage.total_tokens, 30)
        self.assertEqual(res.messages[1].reasoning_content, REASONING)
        self.assertEqual(res.messages[1].tool_calls[0].function.name, "read_file")
        second = FakeDeepSeek.requests[1]
        self.assertEqual(second["messages"][1]["reasoning_content"], REASONING)
        self.assertEqual(second["messages"][2], {"role": "tool", "content": "hello", "tool_call_id": "c1"})

    def test_api_errors_become_llm_errors(self):
        # Seed an assistant message without reasoning_content so the fake returns 400.
        from agent.llm import ChatRequest, Message

        client = Client(self.base_url, "sk-test")
        req = ChatRequest(
            model="m",
            messages=[Message(role="user", content="hi"), Message(role="assistant", content="x")],
            tools=Registry(ReadFile(self.tmp.name)).specs(),
        )
        with self.assertRaises(LLMError) as ctx:
            client.chat(req)
        self.assertIn("400", str(ctx.exception))
        self.assertEqual(len(FakeDeepSeek.requests), 1, "4xx errors must not be retried")


if __name__ == "__main__":
    unittest.main()
