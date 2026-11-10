import os
import tempfile
import time
import unittest

from agent.tools import EditFile, ReadFile, Registry, Shell, ToolError, Workspace, WriteFile


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)
        self.outside = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()
        self.outside.cleanup()

    def test_workspace_resolve(self):
        os.symlink(self.outside.name, os.path.join(self.ws.root, "link"))
        for ok in ["a.txt", "sub/dir/new.py", "./x/../y", os.path.join(self.ws.root, "abs.txt")]:
            self.ws.resolve(ok)
        for bad in ["../escape", "/etc/passwd", "link/secret", "link/new/file"]:
            with self.assertRaises(PermissionError, msg=bad):
                self.ws.resolve(bad)
        with self.assertRaises(ValueError):
            self.ws.resolve("")

    def test_write_read_edit(self):
        write, read, edit = WriteFile(self.ws), ReadFile(self.ws), EditFile(self.ws)
        write.run({"path": "pkg/m.py", "content": "def f():\n    return 1\n\ndef g():\n    return 1\n"})
        self.assertIn("return 1", read.run({"path": "pkg/m.py"}))

        with self.assertRaisesRegex(ValueError, "appears 2 times"):
            edit.run({"path": "pkg/m.py", "old_str": "return 1", "new_str": "return 2"})
        with self.assertRaisesRegex(ValueError, "not found"):
            edit.run({"path": "pkg/m.py", "old_str": "return 3", "new_str": "x"})
        out = edit.run({"path": "pkg/m.py", "old_str": "def g():\n    return 1", "new_str": "def g():\n    return 2"})
        self.assertEqual(out, "edited pkg/m.py at line 4")
        self.assertEqual(read.run({"path": "pkg/m.py"}), "def f():\n    return 1\n\ndef g():\n    return 2\n")

        with self.assertRaises(PermissionError):
            write.run({"path": "../evil.txt", "content": "x"})

    def test_read_rejects_binary_and_dirs(self):
        with open(os.path.join(self.ws.root, "bin"), "wb") as f:
            f.write(b"\0\1\2")
        with self.assertRaises(ValueError):
            ReadFile(self.ws).run({"path": "bin"})
        with self.assertRaises(IsADirectoryError):
            ReadFile(self.ws).run({"path": "."})

    def test_shell(self):
        sh = Shell(self.ws, env={"AGENT_TEST_VAR": "hi"})
        out = sh.run({"command": "pwd; echo $AGENT_TEST_VAR; echo oops >&2; exit 3"})
        self.assertTrue(out.startswith("exit_code: 3\n"), out)
        self.assertIn(self.ws.root, out)
        self.assertIn("hi", out)
        self.assertIn("oops", out)

        start = time.monotonic()
        out = sh.run({"command": "sleep 30", "timeout_sec": 1})
        self.assertIn("timeout", out)
        self.assertLess(time.monotonic() - start, 10)

    def test_shell_approval(self):
        asked = []
        sh = Shell(self.ws, approve=lambda c: asked.append(c) or False)
        with self.assertRaises(PermissionError):
            sh.run({"command": "touch x"})
        self.assertEqual(asked, ["touch x"])
        self.assertFalse(os.path.exists(os.path.join(self.ws.root, "x")))

    def test_registry_errors(self):
        reg = Registry(ReadFile(self.ws))
        with self.assertRaises(ToolError):
            reg.call("nope", "{}")
        with self.assertRaises(ToolError):
            reg.call("read_file", "{not json")
        with self.assertRaises(ToolError):
            reg.call("read_file", "[1]")


if __name__ == "__main__":
    unittest.main()
