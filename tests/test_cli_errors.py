import subprocess
import sys
import unittest
from pathlib import Path


class CliErrorTests(unittest.TestCase):
    def test_invalid_input_is_one_line_without_traceback(self):
        script = Path(__file__).resolve().parent.parent / "text_to_json.py"
        proc = subprocess.run(
            [sys.executable, str(script), "random garbage input"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Cannot parse input as posts/news/subs", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
