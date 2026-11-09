import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import dotenv


class DotenvTest(unittest.TestCase):
    def test_parse_line(self):
        cases = {
            "KEY=value": ("KEY", "value"),
            "export KEY=value": ("KEY", "value"),
            'KEY="quoted # not a comment"': ("KEY", "quoted # not a comment"),
            "KEY='single'": ("KEY", "single"),
            "KEY=value # comment": ("KEY", "value"),
            "KEY=": ("KEY", ""),
            "# comment": None,
            "": None,
            "no equals sign": None,
        }
        for line, want in cases.items():
            self.assertEqual(dotenv.parse_line(line), want, line)

    def test_load_file_keeps_existing_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, ".env")
            path.write_text("DOTENV_TEST_NEW=from-file\nDOTENV_TEST_SET=from-file\n")
            with mock.patch.dict(os.environ, {"DOTENV_TEST_SET": "from-shell"}):
                os.environ.pop("DOTENV_TEST_NEW", None)
                dotenv.load_file(path)
                self.assertEqual(os.environ["DOTENV_TEST_NEW"], "from-file")
                self.assertEqual(os.environ["DOTENV_TEST_SET"], "from-shell")

    def test_find_stops_at_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            repo = outer / "repo"
            sub = repo / "a" / "b"
            sub.mkdir(parents=True)
            (outer / ".env").write_text("X=1")
            self.assertEqual(dotenv.find(sub), outer / ".env")

            (repo / ".git").mkdir()
            self.assertIsNone(dotenv.find(sub), "find crossed the repo root")
            (repo / ".env").write_text("X=1")
            self.assertEqual(dotenv.find(sub), repo / ".env")


if __name__ == "__main__":
    unittest.main()
