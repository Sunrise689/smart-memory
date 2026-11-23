import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run(*args):
    return subprocess.run([sys.executable, str(ROOT / "smy.py"), *args], text=True, capture_output=True, check=True)


class SMyTests(unittest.TestCase):
    def test_index_search_and_redaction(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            tmp_path = Path(td)
            memory = tmp_path / "memory"; raw = tmp_path / "raw"; memory.mkdir(); raw.mkdir()
            (memory / "note.md").write_text("---\nlayer: method\n---\n# Deploy workflow\nUse the safe path. api_key=super-secret-token-123456", encoding="utf-8")
            (raw / "session.txt").write_text("A raw session says deploy workflow and token=secret", encoding="utf-8")
            config = tmp_path / "config.json"
            config.write_text(json.dumps({"index": str(tmp_path / "index.sqlite"), "memory_roots": [{"name": "memory", "path": str(memory)}], "raw_roots": [{"name": "raw", "path": str(raw)}]}), encoding="utf-8")
            self.assertEqual(json.loads(run("--config", str(config), "index").stdout)["docs"], 1)
            result = [json.loads(line) for line in run("--config", str(config), "search", "deploy workflow", "--json").stdout.splitlines()]
            self.assertTrue(result)
            self.assertIn("[REDACTED]", result[0]["snippet"])
            raw_result = [json.loads(line) for line in run("--config", str(config), "search", "deploy workflow", "--raw", "--json").stdout.splitlines()]
            self.assertTrue(raw_result)
            self.assertEqual(raw_result[0]["source"], "raw")


    def test_health(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            tmp_path = Path(td)
            config = tmp_path / "config.json"; config.write_text("{}", encoding="utf-8")
            data = json.loads(run("--config", str(config), "health").stdout)
            self.assertFalse(data["index_exists"])


if __name__ == "__main__":
    unittest.main()
