import unittest
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
import os
import tempfile

import view_latest_task


class LatestTaskViewTests(unittest.TestCase):
    @staticmethod
    def strip_ansi(text: str) -> str:
        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def test_renders_latest_parent_and_children(self):
        tasks = [
            {"id": "1", "name": "Old", "createdAt": "2026-05-01T00:00:00Z", "workMinutes": 60, "children": []},
            {
                "id": "2",
                "name": "New Parent",
                "createdAt": "2026-05-13T00:40:00Z",
                "workMinutes": 1056,
                "children": [
                    {
                        "id": "3",
                        "name": "Child",
                        "createdAt": "2026-05-13T01:00:00Z",
                        "workMinutes": 134,
                        "children": [],
                    }
                ],
            },
        ]
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Latest task", out)
        self.assertIn("Name: New Parent", out)
        self.assertIn("Subtasks", out)
        self.assertIn("Child", out)
        self.assertIn("Work time: 2h 14m", out)
        self.assertIn("Extended deadline:", out)

    def test_countdown_line_present(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "createdAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "children": [],
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Work time left:", out)

    def test_countdown_does_not_show_overdue_label(self):
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        target = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(view_latest_task.fmt_countdown(now_local, target), "0h 0m 0s")

    def test_only_one_empty_line_before_actions(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "createdAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "children": [],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        lines = out.splitlines()
        actions_idx = lines.index("Actions: create task | add subtasks | copy extension msg | copy completion msg | quit")
        self.assertEqual(lines[actions_idx - 1], "")
        self.assertNotEqual(lines[actions_idx - 2], "")

    def test_actions_highlight_expected_shortcuts(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "createdAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "children": [],
            }
        ]
        out = view_latest_task.build_latest_view(tasks)
        self.assertRegex(out, r"\x1b\[35mcreate \x1b\[0m\x1b\[32mt\x1b\[0m\x1b\[35mask")
        self.assertRegex(out, r"\x1b\[35madd \x1b\[0m\x1b\[32ms\x1b\[0m\x1b\[35mubtasks")
        self.assertRegex(out, r"\x1b\[35mcopy \x1b\[0m\x1b\[32me\x1b\[0m\x1b\[35mxtension msg")
        self.assertRegex(out, r"\x1b\[35mcopy \x1b\[0m\x1b\[32mc\x1b\[0m\x1b\[35mompletion msg")

    def test_no_consecutive_empty_lines_with_status(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "createdAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "children": [],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, status="Task is missing deadline."))
        lines = out.splitlines()
        for idx in range(1, len(lines)):
            self.assertFalse(lines[idx - 1] == "" and lines[idx] == "")

    def test_uses_default_title_and_default_labels(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "createdAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "children": [],
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = view_latest_task.build_latest_view(tasks, now_local)
        self.assertIn("Latest task", out)
        self.assertIn("Name: Only", out)
        self.assertIn("Created: 2026-05-13 Wed 08:40", out)
        self.assertIn("Deadline: ", out)
        self.assertIn("Work time: 2h", out)

    def test_work_seconds_between_skips_off_hours(self):
        start = datetime(2026, 5, 13, 16, 0, tzinfo=timezone(timedelta(hours=8)))
        end = datetime(2026, 5, 14, 9, 0, tzinfo=timezone(timedelta(hours=8)))
        # Work windows counted: 16:00-17:00 (1h) + 8:00-9:00 (1h) = 2h.
        self.assertEqual(view_latest_task.work_seconds_between(start, end), 2 * 3600)

    def test_extended_deadline_uses_stored_child_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "createdAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-13T02:00:00Z",  # 10:00 local
                "workMinutes": 60,
                "children": [
                    {
                        "id": "2",
                        "name": "Child",
                        "createdAt": "2026-05-13T01:00:00Z",
                        "workMinutes": 60,
                        "children": [],
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Extended deadline: 2026-05-13 Wed 11:00", out)

    def test_input_path_uses_script_dir_tasks_json(self):
        fake_script = Path("/tmp/proj/view_latest_task.py")
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            resolved = view_latest_task.resolve_input_path(fake_script=fake_script)
        os.chdir(old_cwd)
        self.assertEqual(resolved, Path("/tmp/proj/tasks.json"))


if __name__ == "__main__":
    unittest.main()
