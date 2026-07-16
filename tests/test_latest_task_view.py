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

    def test_renders_latest_parent_and_extensions(self):
        tasks = [
            {"id": "1", "name": "Old", "startAt": "2026-05-01T00:00:00Z", "workMinutes": 60},
            {
                "id": "2",
                "name": "New Parent",
                "notes": ['"上肢" referred to arms rather than upper body.'],
                "stages": [
                    {
                        "type": "subs",
                        "stage": "translate",
                        "assignee": "Alex",
                        "startAt": "2026-05-13T00:40:00Z",
                        "workMinutes": 1056,
                        "extensions": [
                            {
                                "name": "Child",
                                "type": "news",
                                "assignee": "Alex",
                                "startAt": "2026-05-13T01:00:00Z",
                                "workMinutes": 134,
                                "notes": ["extension-only note"],
                            }
                        ],
                    }
                ],
            },
        ]
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Task", out)
        self.assertIn("Name: New Parent", out)
        self.assertIn("Stage: translate", out)
        self.assertIn("Assignee: Alex", out)
        self.assertIn("Extensions", out)
        self.assertIn("Notes (1)", out)
        self.assertIn('• "上肢" referred to arms rather than upper body.', out)
        self.assertNotIn('• extension-only note', out)
        self.assertIn("Child", out)
        self.assertIn("Type: subs", out)
        self.assertIn("Type: news", out)
        self.assertIn("Work time: 2h 14m", out)
        self.assertIn("Extended deadline:", out)

    def test_expanded_notes_render_bullets(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "notes": ["first note", "second note"],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, show_subtask_notes=True))
        self.assertIn("Notes (2)", out)
        self.assertIn("• first note", out)
        self.assertIn("• second note", out)

    def test_expanded_view_renders_subtask_notes(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Child",
                                "type": "news",
                                "startAt": "2026-05-13T01:00:00Z",
                                "workMinutes": 30,
                                "notes": ["subtask note"],
                            }
                        ]
                    }
                ],
            }
        ]
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local, show_subtask_notes=True))
        self.assertIn("Notes (1)", out)
        self.assertIn("• subtask note", out)

    def test_missing_core_fields_render_hyphen_lines(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "workMinutes": 120,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Child",
                                "workMinutes": 30,
                            }
                        ]
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Type: -", out)
        self.assertIn("Stage: -", out)
        self.assertIn("Assignee: -", out)
        self.assertIn("Notes: -", out)

    def test_empty_notes_field_has_no_extra_blank_line_when_no_subtasks(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "workMinutes": 120,
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Work time left: -\nNotes: -", out)

    def test_main_notes_render_before_extensions(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "workMinutes": 120,
                "notes": ["parent note"],
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Child",
                                "type": "news",
                                "workMinutes": 30,
                            }
                        ]
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Work time left: -\nNotes (1)", out)
        self.assertLess(out.index("Notes (1)"), out.index("Extensions"))

    def test_hidden_extension_notes_do_not_add_extra_blank_line(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "workMinutes": 120,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Child A",
                                "type": "news",
                                "workMinutes": 30,
                                "notes": ["note one"],
                            },
                            {
                                "name": "Child B",
                                "type": "news",
                                "workMinutes": 40,
                            },
                        ]
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Notes (1)\n\nName: Child B", out)

    def test_extensions_hide_non_today_items(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "startAt": "2026-06-18T08:53:00Z",
                "workMinutes": 1680,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Old extension",
                                "type": "news",
                                "startAt": "2026-06-22T00:22:00Z",
                                "workMinutes": 30,
                            },
                            {
                                "name": "Older extension",
                                "type": "posts",
                                "startAt": "2026-06-23T00:31:00Z",
                                "workMinutes": 70,
                            },
                        ]
                    }
                ],
            }
        ]
        now_local = datetime(2026, 6, 25, 8, 22, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertNotIn("Extensions", out)
        self.assertNotIn("Old extension", out)
        self.assertNotIn("Older extension", out)

    def test_countdown_line_present(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Work time left:", out)

    def test_countdown_shows_resume_hint_outside_work_hours(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T05:00:00Z",
                "workMinutes": 120,
            }
        ]
        # 2026-05-13 Wed 12:30 local is lunch break; next work start is 13:00.
        now_local = datetime(2026, 5, 13, 12, 30, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Work time left:", out)
        self.assertIn("(resumes 2026-05-13 Wed 13:00)", out)

    def test_countdown_hides_resume_hint_during_work_hours(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        work_line = next(line for line in out.splitlines() if line.startswith("Work time left:"))
        self.assertNotIn("(resumes ", work_line)

    def test_reminds_after_ask_by_time_for_before_nine_deadline(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "deadline": "2026-05-13T17:00:00Z",
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Deadline: 2026-05-14 Thu 01:00 (ask for another task)", out)

    def test_reminder_hides_before_ask_by_time_for_after_nine_deadline(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "deadline": "2026-05-14T05:00:00Z",
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Deadline: 2026-05-14 Thu 13:00", out)
        self.assertNotIn("(ask for another task)", out)

    def test_reminds_after_ask_by_time_for_after_nine_deadline(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "deadline": "2026-05-14T05:00:00Z",
            }
        ]
        now_local = datetime(2026, 5, 14, 9, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Deadline: 2026-05-14 Thu 13:00 (ask for another task)", out)

    def test_countdown_does_not_show_overdue_label(self):
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        target = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(view_latest_task.fmt_countdown(now_local, target), "0h 0m 0s")

    def test_only_one_empty_line_before_actions(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        lines = out.splitlines()
        actions_idx = lines.index(
            "Actions: create task | add extensions | add notes | toggle view notes | copy message | quit"
        )
        self.assertEqual(lines[actions_idx - 1], "")
        self.assertNotEqual(lines[actions_idx - 2], "")

    def test_personal_actions_highlight_expected_shortcuts(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        out = view_latest_task.build_latest_view(tasks)
        self.assertRegex(out, r"\x1b\[35mcreate \x1b\[0m\x1b\[32mt\x1b\[0m\x1b\[35mask")
        self.assertRegex(out, r"\x1b\[35madd \x1b\[0m\x1b\[32me\x1b\[0m\x1b\[35mxtensions")
        self.assertRegex(out, r"\x1b\[35madd \x1b\[0m\x1b\[32mn\x1b\[0m\x1b\[35motes")
        self.assertRegex(out, r"\x1b\[35mtoggle \x1b\[0m\x1b\[32mv\x1b\[0m\x1b\[35miew notes")
        self.assertRegex(out, r"\x1b\[35mcopy \x1b\[0m\x1b\[32mm\x1b\[0m\x1b\[35message")
        self.assertNotRegex(out, r"\x1b\[35mset \x1b\[0m\x1b\[32ma\x1b\[0m\x1b\[35mssignee")
        self.assertNotRegex(out, r"\x1b\[35mconfirm \x1b\[0m\x1b\[32md\x1b\[0m\x1b\[35meadline extension")

    def test_coworker_actions_highlight_expected_shortcuts(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        out = view_latest_task.build_latest_view(tasks, input_file="/tmp/tasks_coworkers.json")
        self.assertRegex(out, r"\x1b\[35mset \x1b\[0m\x1b\[32ma\x1b\[0m\x1b\[35mssignee")
        self.assertRegex(out, r"\x1b\[35mset \x1b\[0m\x1b\[32ms\x1b\[0m\x1b\[35mtart time")
        self.assertRegex(out, r"\x1b\[35mconfirm \x1b\[0m\x1b\[32md\x1b\[0m\x1b\[35meadline extension")
        self.assertRegex(out, r"\x1b\[35mcreate \x1b\[0m\x1b\[32mt\x1b\[0m\x1b\[35mask")
        self.assertNotRegex(out, r"\x1b\[35madd \x1b\[0m\x1b\[32mn\x1b\[0m\x1b\[35motes")
        self.assertNotRegex(out, r"\x1b\[35mtoggle \x1b\[0m\x1b\[32mv\x1b\[0m\x1b\[35miew notes")
        self.assertNotRegex(out, r"\x1b\[35madd \x1b\[0m\x1b\[32me\x1b\[0m\x1b\[35mxtensions")

    def test_coworker_actions_include_copy_message_when_message_exists(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "type": "subs",
                        "assignee": "Shawn",
                        "startAt": "2026-06-09T03:35:00Z",
                        "deadline": "2026-06-10T01:40:00Z",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                    }
                ],
            }
        ]
        out = view_latest_task.build_latest_view(tasks, input_file="/tmp/tasks_coworkers.json")
        self.assertRegex(out, r"\x1b\[35mcopy \x1b\[0m\x1b\[32mm\x1b\[0m\x1b\[35message")

    def test_coworker_latest_view_can_filter_by_program(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛真健康（低衝擊有氧 + 美背有氧 + 手臂減脂）",
                "assigner": "Emily Ding",
            },
            {
                "id": "2",
                "name": "3集大愛醫生館（胰管狹窄 + 頭痛的背影 + 崩解的膝平臺）",
                "assigner": "Alex Chen",
            },
        ]
        out = self.strip_ansi(
            view_latest_task.build_latest_view(
                tasks,
                input_file="/tmp/tasks_coworkers.json",
                program="大愛真健康",
            )
        )
        self.assertIn("3集大愛真健康", out)
        self.assertNotIn("3集大愛醫生館", out)

    def test_coworker_latest_view_missing_program_uses_error_label(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（胰管狹窄 + 頭痛的背影 + 崩解的膝平臺）",
            },
        ]
        out = self.strip_ansi(
            view_latest_task.build_latest_view(
                tasks,
                input_file="/tmp/tasks_coworkers.json",
                program="大愛真健康",
            )
        )
        self.assertIn("Error: No task found for program: 大愛真健康", out)

    def test_coworker_latest_view_missing_program_error_is_red(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（胰管狹窄 + 頭痛的背影 + 崩解的膝平臺）",
            },
        ]
        out = view_latest_task.build_latest_view(
            tasks,
            input_file="/tmp/tasks_coworkers.json",
            program="大愛真健康",
        )
        self.assertIn("\x1b[31mError: No task found for program: 大愛真健康\x1b[0m", out)

    def test_coworker_actions_hide_copy_message_when_no_message_exists(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        out = view_latest_task.build_latest_view(tasks, input_file="/tmp/tasks_coworkers.json")
        self.assertNotRegex(out, r"\x1b\[35mcopy \x1b\[0m\x1b\[32mm\x1b\[0m\x1b\[35message")

    def test_no_consecutive_empty_lines_with_message_status(self):
        tasks = [
            {
                "id": "1",
                "name": "Only",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
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
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 120,
            }
        ]
        now_local = datetime(2026, 5, 13, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        out = view_latest_task.build_latest_view(tasks, now_local)
        self.assertIn("Task", out)
        self.assertIn("Name: Only", out)
        self.assertIn("Start time: 2026-05-13 Wed 08:40", out)
        self.assertIn("Deadline: ", out)
        self.assertIn("Work time: 2h", out)

    def test_initial_coworker_task_does_not_show_fake_start_or_deadline(self):
        tasks = [
            {
                "id": "1",
                "name": "三集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                    }
                ],
            }
        ]
        now_local = datetime(2026, 6, 19, 8, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local, input_file="/tmp/tasks_coworkers.json"))
        self.assertIn("Start time: -", out)
        self.assertIn("Deadline: -", out)
        self.assertIn("Work time left: -", out)

    def test_coworker_view_hides_notes_for_parent_and_subtasks(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                        "extensions": [
                            {
                                "name": "新聞英文與配音",
                                "type": "custom",
                                "workMinutes": 95,
                            }
                        ],
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, input_file="/tmp/tasks_coworkers.json"))
        self.assertNotIn("Notes: -", out)

    def test_coworker_view_hides_stage_and_assignee_for_subtasks(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                        "extensions": [
                            {
                                "name": "新聞英文與配音",
                                "type": "custom",
                                "workMinutes": 95,
                            }
                        ],
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, input_file="/tmp/tasks_coworkers.json"))
        self.assertIn("Name: 新聞英文與配音", out)
        self.assertNotIn("Name: 新聞英文與配音\nType: custom\nStage:", out)
        self.assertNotIn("Assignee:", out.split("Extensions", 1)[1])

    def test_latest_view_shows_only_current_workday_extensions(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 364,
                        "extensions": [
                            {
                                "name": "Older extension",
                                "type": "news",
                                "startAt": "2026-06-23T00:31:48.475067Z",
                                "workMinutes": 70,
                            },
                            {
                                "name": "Today extension",
                                "type": "news",
                                "startAt": "2026-06-24T00:19:56.331294Z",
                                "workMinutes": 68,
                            }
                        ],
                    }
                ],
            }
        ]
        now_local = datetime(2026, 6, 24, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Name: Today extension", out)
        self.assertNotIn("Name: Older extension", out)

    def test_work_seconds_between_skips_off_hours(self):
        start = datetime(2026, 5, 13, 16, 0, tzinfo=timezone(timedelta(hours=8)))
        end = datetime(2026, 5, 14, 9, 0, tzinfo=timezone(timedelta(hours=8)))
        # Work windows counted: 16:00-17:00 (1h) + 8:00-9:00 (1h) = 2h.
        self.assertEqual(view_latest_task.work_seconds_between(start, end), 2 * 3600)

    def test_extended_deadline_uses_stored_extension_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "stages": [
                    {
                        "startAt": "2026-05-13T00:40:00Z",
                        "deadline": "2026-05-13T02:00:00Z",
                        "workMinutes": 60,
                        "extensions": [
                            {
                                "name": "Child",
                                "startAt": "2026-05-13T01:00:00Z",
                                "workMinutes": 60,
                            }
                        ]
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Extended deadline: 2026-05-13 Wed 11:00", out)

    def test_custom_subtask_hides_deadline_line(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "startAt": "2026-06-19T00:00:00Z",
                "deadline": "2026-06-10T01:40:00Z",
                "workMinutes": 364,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "新聞英文與配音",
                                "workMinutes": 95,
                            }
                        ]
                    }
                ],
            }
        ]
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks))
        self.assertIn("Extensions", out)
        self.assertIn("Name: 新聞英文與配音", out)
        self.assertIn("Work time: 1h 35m", out)
        self.assertNotIn("Deadline: 2026-06-19 Fri 09:35", out)

    def test_extension_deadline_is_computed_from_start_and_work_time(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "workMinutes": 60,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Child",
                                "type": "news",
                                "startAt": "2026-05-13T01:00:00Z",
                                "workMinutes": 60,
                            }
                        ]
                    }
                ],
            }
        ]
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn("Deadline: 2026-05-13 Wed 10:00", out)

    def test_extension_blocks_have_single_blank_line_separator(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "startAt": "2026-05-13T00:40:00Z",
                "workMinutes": 60,
                "stages": [
                    {
                        "extensions": [
                            {
                                "name": "Child A",
                                "type": "news",
                                "startAt": "2026-05-13T01:00:00Z",
                                "workMinutes": 60,
                                "deadline": "2026-05-13T02:00:00Z",
                            },
                            {
                                "name": "Child B",
                                "type": "posts",
                                "startAt": "2026-05-13T02:00:00Z",
                                "workMinutes": 30,
                                "deadline": "2026-05-13T03:00:00Z",
                            },
                        ]
                    }
                ],
            }
        ]
        now_local = datetime(2026, 5, 13, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        out = self.strip_ansi(view_latest_task.build_latest_view(tasks, now_local))
        self.assertIn(
            "Deadline: 2026-05-13 Wed 10:00\nNotes: -\n\nName: Child B",
            out,
        )

    def test_input_path_uses_script_dir_tasks_json(self):
        fake_script = Path("/tmp/proj/view_latest_task.py")
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            resolved = view_latest_task.resolve_input_path(fake_script=fake_script)
        os.chdir(old_cwd)
        self.assertEqual(resolved, Path("/tmp/proj/tasks.json"))

    def test_input_path_uses_explicit_file_in_script_dir(self):
        fake_script = Path("/tmp/proj/view_task.py")
        resolved = view_latest_task.resolve_input_path("tasks_coworkers.json", fake_script=fake_script)
        self.assertEqual(resolved, Path("/tmp/proj/tasks_coworkers.json"))

    def test_build_task_view_can_select_task_by_id(self):
        tasks = [
            {"id": "1", "name": "Old", "startAt": "2026-05-01T00:00:00Z", "workMinutes": 60},
            {"id": "2", "name": "New", "startAt": "2026-05-13T00:40:00Z", "workMinutes": 120},
        ]
        out = self.strip_ansi(view_latest_task.build_task_view(tasks, task_id="1"))
        self.assertIn("Name: Old", out)
        self.assertNotIn("Name: New", out)


if __name__ == "__main__":
    unittest.main()
