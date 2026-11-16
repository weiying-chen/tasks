import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import work_time


class WorkTimeTests(unittest.TestCase):
    def test_shift_deadline_preserves_time_on_personal_day_off(self):
        deadline = datetime(2026, 11, 17, 10, 36)
        shifted = work_time.shift_deadline_to_workday(deadline)
        self.assertEqual(shifted, datetime(2026, 11, 18, 10, 36))

    def test_add_work_minutes_skips_personal_day_off_november_17(self):
        start = datetime(2026, 11, 17, 9, 0)
        deadline = work_time.add_work_minutes(start, 60)
        self.assertEqual(deadline, datetime(2026, 11, 18, 9, 0))

    def test_add_work_minutes_skips_configured_holiday(self):
        taipei = ZoneInfo("Asia/Taipei")
        start = datetime(2026, 10, 8, 16, 25, tzinfo=taipei)

        deadline = work_time.add_work_minutes(start, 115)

        self.assertEqual(deadline, datetime(2026, 10, 12, 9, 20, tzinfo=taipei))

    def test_add_work_minutes_skips_taiwan_lunar_new_year_holidays(self):
        taipei = ZoneInfo("Asia/Taipei")
        start = datetime(2026, 2, 13, 16, 30, tzinfo=taipei)

        deadline = work_time.add_work_minutes(start, 120)

        self.assertEqual(deadline, datetime(2026, 2, 23, 9, 30, tzinfo=taipei))

    def test_add_work_minutes_uses_next_year_taiwan_calendar(self):
        taipei = ZoneInfo("Asia/Taipei")
        start = datetime(2026, 12, 31, 16, 30, tzinfo=taipei)

        deadline = work_time.add_work_minutes(start, 120)

        self.assertEqual(deadline, datetime(2027, 1, 4, 9, 30, tzinfo=taipei))


if __name__ == "__main__":
    unittest.main()
