import unittest
from datetime import datetime, timezone, timedelta
import re

import latest_task_view as ltv


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
        out = self.strip_ansi(ltv.build_latest_view(tasks, now_local))
        self.assertIn("Latest task", out)
        self.assertIn("Name: New Parent", out)
        self.assertIn("Child tasks", out)
        self.assertIn("Child", out)
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
        out = self.strip_ansi(ltv.build_latest_view(tasks, now_local))
        self.assertIn("Work time left:", out)

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
        out = ltv.build_latest_view(tasks, now_local)
        self.assertIn("Latest task", out)
        self.assertIn("Name: Only", out)
        self.assertIn("Created: 2026-05-13 Wed 08:40", out)
        self.assertIn("Deadline: ", out)
        self.assertIn("Work time: 2h", out)

    def test_work_seconds_between_skips_off_hours(self):
        start = datetime(2026, 5, 13, 16, 0, tzinfo=timezone(timedelta(hours=8)))
        end = datetime(2026, 5, 14, 9, 0, tzinfo=timezone(timedelta(hours=8)))
        # Work windows counted: 16:00-17:00 (1h) + 8:00-9:00 (1h) = 2h.
        self.assertEqual(ltv.work_seconds_between(start, end), 2 * 3600)


if __name__ == "__main__":
    unittest.main()
