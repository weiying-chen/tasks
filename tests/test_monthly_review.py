import tempfile
import unittest
import re
from datetime import datetime
from pathlib import Path

import view_latest_task


class MonthlyReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = {
            "id": "1",
            "name": "Current task",
            "type": "subs",
            "stages": [{"workMinutes": 60}],
        }

    def test_reminder_appears_during_last_five_days(self):
        now = datetime(2026, 10, 27, 9, 0, tzinfo=view_latest_task.TZ_TAIPEI)

        output = view_latest_task.build_latest_view(
            [self.task],
            now_local=now,
            input_file="/tmp/tasks.json",
            submitted_review_months=set(),
        )

        plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
        self.assertIn(
            "Monthly review due by 2026-10-31 (not yet submitted)", plain
        )
        self.assertIn("mark review as submitted", plain)
        self.assertLess(plain.index("Monthly review due"), plain.index("Task"))

    def test_reminder_is_hidden_before_last_five_days(self):
        now = datetime(2026, 10, 26, 9, 0, tzinfo=view_latest_task.TZ_TAIPEI)

        output = view_latest_task.build_latest_view(
            [self.task],
            now_local=now,
            input_file="/tmp/tasks.json",
            submitted_review_months=set(),
        )

        plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
        self.assertNotIn("Monthly review due", plain)
        self.assertNotIn("mark review as submitted", plain)

    def test_submitted_month_hides_reminder(self):
        now = datetime(2026, 10, 29, 9, 0, tzinfo=view_latest_task.TZ_TAIPEI)

        output = view_latest_task.build_latest_view(
            [self.task],
            now_local=now,
            input_file="/tmp/tasks.json",
            submitted_review_months={"2026-10"},
        )

        plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
        self.assertNotIn("Monthly review due", plain)
        self.assertNotIn("mark review as submitted", plain)

    def test_mark_submitted_persists_month(self):
        now = datetime(2026, 10, 29, 9, 0, tzinfo=view_latest_task.TZ_TAIPEI)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "monthly-review.json"

            view_latest_task.mark_monthly_review_submitted(path, now)

            self.assertEqual(
                view_latest_task.load_submitted_review_months(path), {"2026-10"}
            )


if __name__ == "__main__":
    unittest.main()
