import subprocess
import sys
import tempfile
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

    def test_view_latest_task_accepts_file_arg(self):
        script = Path(__file__).resolve().parent.parent / "view_latest_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks_coworkers.json"
            tasks_path.write_text('[{"id":"1","name":"Coworker","stages":[{"type":"subs","startAt":"2026-06-02T01:00:00Z","workMinutes":240}]}]', encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--file", str(tasks_path), "--once"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Name: Coworker", proc.stdout)

    def test_view_task_wrapper_accepts_file_arg(self):
        script = Path(__file__).resolve().parent.parent / "view_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks_coworkers.json"
            tasks_path.write_text('[{"id":"1","name":"Coworker","stages":[{"type":"subs","startAt":"2026-06-02T01:00:00Z","workMinutes":240}]}]', encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--file", str(tasks_path), "--once"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Name: Coworker", proc.stdout)

    def test_notes_target_error_is_one_line_without_traceback(self):
        script = Path(__file__).resolve().parent.parent / "text_to_json.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--parent-id", "6", "--target", "notes", "not a bullet line"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Cannot add notes.", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
