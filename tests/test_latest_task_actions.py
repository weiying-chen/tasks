import unittest
from unittest import mock
from datetime import datetime, timezone, timedelta

import view_latest_task


class LatestTaskActionsTests(unittest.TestCase):
    def test_copy_success_status_messages(self):
        self.assertEqual(
            view_latest_task.DEADLINE_MESSAGE_COPIED_STATUS,
            "Success: Deadline extension message copied to clipboard",
        )
        self.assertEqual(
            view_latest_task.NEXT_TASK_MESSAGE_COPIED_STATUS,
            "Success: Next task message copied to clipboard",
        )
        self.assertEqual(
            view_latest_task.TASK_INITIATION_MESSAGE_COPIED_STATUS,
            "Success: Task initiation message copied to clipboard",
        )

    def test_find_latest_task_id(self):
        tasks = [
            {"id": "1", "name": "A", "children": []},
            {"id": "7", "name": "B", "children": []},
        ]
        self.assertEqual(view_latest_task.find_latest_task_id(tasks), "7")

    def test_build_add_to_latest_command(self):
        cmd = view_latest_task.build_add_to_latest_command("/tmp", "9", "children", "/tmp/tasks_coworkers.json")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/text_to_json.py",
                "--infile",
                "/tmp/tasks_coworkers.json",
                "--parent-id",
                "9",
                "--target",
                "children",
                "__CLIPBOARD__",
            ],
        )

    def test_build_add_notes_to_latest_command(self):
        cmd = view_latest_task.build_add_to_latest_command("/tmp", "9", "notes", "/tmp/tasks_coworkers.json")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/text_to_json.py",
                "--infile",
                "/tmp/tasks_coworkers.json",
                "--parent-id",
                "9",
                "--target",
                "notes",
                "__CLIPBOARD__",
            ],
        )

    def test_build_add_task_command(self):
        cmd = view_latest_task.build_add_task_command("/tmp", "/tmp/tasks_coworkers.json")
        self.assertEqual(cmd, ["/tmp/add_task.sh", "--file", "/tmp/tasks_coworkers.json"])

    def test_build_add_notes_command(self):
        cmd = view_latest_task.build_add_notes_command("/tmp", "9", "/tmp/tasks_coworkers.json")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/text_to_json.py",
                "--infile",
                "/tmp/tasks_coworkers.json",
                "--parent-id",
                "9",
                "--target",
                "notes",
                "__CLIPBOARD__",
            ],
        )

    def test_build_assign_coworker_command(self):
        cmd = view_latest_task.build_assign_coworker_command("/tmp", "/tmp/tasks_coworkers.json")
        self.assertEqual(
            cmd,
            ["python3", "/tmp/assign_task.py", "--infile", "/tmp/tasks_coworkers.json", "__CLIPBOARD__"],
        )

    def test_build_notes_target_options_parent_and_children(self):
        latest = {
            "id": "6",
            "name": "Parent",
            "children": [
                {"id": "7", "name": "Child A"},
                {"id": "8", "name": "Child B"},
            ],
        }
        options = view_latest_task.build_notes_target_options(latest)
        self.assertEqual(
            options,
            [
                ("6", "Parent"),
                ("7", "Child A (subtask)"),
                ("8", "Child B (subtask)"),
            ],
        )

    def test_build_message_target_options_for_personal_tasks(self):
        latest = {
            "id": "1",
            "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
            "assigner": "Emily Ding",
            "stages": [
                {
                    "type": "subs",
                    "assignee": "Alex Chen",
                    "workMinutes": 364,
                    "contentSeconds": 364,
                }
            ],
            "children": [],
        }
        self.assertEqual(
            view_latest_task.build_message_target_options(latest, input_file="/tmp/tasks.json"),
            [
                ("deadline-extension", "Deadline extension message"),
                ("task-completion", "Task completion message"),
            ],
        )

    def test_build_message_target_options_for_coworker_tasks(self):
        latest = {
            "id": "1",
            "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
            "assigner": "Emily Ding",
            "stages": [
                {
                    "type": "subs",
                    "assignee": "Alex Chen",
                    "startAt": "2026-06-09T03:35:00Z",
                    "deadline": "2026-06-10T01:40:00Z",
                    "workMinutes": 364,
                    "contentSeconds": 364,
                }
            ],
            "children": [],
        }
        self.assertEqual(
            view_latest_task.build_message_target_options(latest, input_file="/tmp/tasks_coworkers.json"),
            [
                ("task-initiation", "Task initiation message"),
                ("task-assignment", "Task assignment message"),
            ],
        )

    def test_build_message_target_options_hides_task_assignment_when_unassigned_in_coworker_mode(self):
        latest = {
            "id": "1",
            "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
            "assigner": "Emily Ding",
            "stages": [
                {
                    "type": "subs",
                    "workMinutes": 364,
                    "contentSeconds": 364,
                }
            ],
            "children": [],
        }
        self.assertEqual(
            view_latest_task.build_message_target_options(latest, input_file="/tmp/tasks_coworkers.json"),
            [],
        )

    def test_build_message_target_options_hides_task_initiation_when_start_missing_in_coworker_mode(self):
        latest = {
            "id": "1",
            "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
            "assigner": "Emily Ding",
            "stages": [
                {
                    "type": "subs",
                    "startAt": "2026-06-09T03:35:00Z",
                    "workMinutes": 364,
                    "contentSeconds": 364,
                }
            ],
            "children": [],
        }
        self.assertEqual(
            view_latest_task.build_message_target_options(latest, input_file="/tmp/tasks_coworkers.json"),
            [],
        )

    def test_build_task_assignment_message_command(self):
        cmd = view_latest_task.build_task_assignment_message_command("/tmp", "/tmp/tasks.json", "9")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/create_message.py",
                "-i",
                "/tmp/tasks.json",
                "--type",
                "task-assignment",
                "--task-id",
                "9",
            ],
        )

    def test_build_task_initiation_message_command(self):
        cmd = view_latest_task.build_task_initiation_message_command("/tmp", "/tmp/tasks.json", "9")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/create_message.py",
                "-i",
                "/tmp/tasks.json",
                "--type",
                "task-initiation",
                "--task-id",
                "9",
            ],
        )

    def test_stage_accessors_use_active_stage(self):
        task = {
            "name": "Parent",
            "stages": [
                {
                    "type": "translate",
                    "assignee": "Alex",
                    "startAt": "2026-06-02T05:40:00Z",
                    "deadline": "2026-06-03T03:40:00Z",
                    "workMinutes": 960,
                    "contentSeconds": 1200,
                }
            ],
        }
        self.assertEqual(view_latest_task.get_task_type(task), "translate")
        self.assertEqual(view_latest_task.get_task_work_minutes(task), 960)

    def test_build_deadline_message_command(self):
        cmd = view_latest_task.build_deadline_message_command("/tmp", "/tmp/tasks.json", "9")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/create_message.py",
                "-i",
                "/tmp/tasks.json",
                "--type",
                "deadline-extension",
                "--task-id",
                "9",
            ],
        )

    def test_build_task_completion_message_command(self):
        cmd = view_latest_task.build_task_completion_message_command("/tmp", "/tmp/tasks.json", "9", "new task", "Alex")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/create_message.py",
                "-i",
                "/tmp/tasks.json",
                "--type",
                "task-completion",
                "--task-id",
                "9",
                "--next-task-name",
                "new task",
                "--next-assigner",
                "Alex",
            ],
        )

    def test_build_confirm_deadline_extension_status_warns_on_mismatch(self):
        task = {
            "id": "1",
            "name": "三集大愛醫生館",
            "stages": [
                {
                    "type": "subs",
                    "deadline": "2026-06-10T01:40:00Z",
                    "workMinutes": 120,
                    "contentSeconds": 120,
                }
            ],
            "children": [],
        }
        clipboard_text = (
            "因deadline 已至，我先加時間 做其他事時間是 2時\n\n"
            "新聞英文與配音 2時\n\n"
            "三集大愛醫生館 deadline 由 6/10（三）09:40，延後至6/10（三）11:15，再請 Alex Chen方便時幫我確認，謝謝。"
        )
        status = view_latest_task.build_confirm_deadline_extension_status(
            task,
            clipboard_text,
            now_local=datetime(2026, 6, 10, 10, 0, tzinfo=timezone(timedelta(hours=8))),
        )
        self.assertEqual(
            status,
            "Warning: Coworker deadline differs (provided 6/10（三）11:15, computed 6/10（三）11:40).",
        )

    def test_build_confirm_deadline_extension_status_reports_success_on_match(self):
        task = {
            "id": "1",
            "name": "三集大愛醫生館",
            "stages": [
                {
                    "type": "subs",
                    "deadline": "2026-06-10T01:40:00Z",
                    "workMinutes": 120,
                    "contentSeconds": 120,
                }
            ],
            "children": [],
        }
        clipboard_text = (
            "因deadline 已至，我先加時間 做其他事時間是 1時35分\n\n"
            "新聞英文與配音 1時35分\n\n"
            "三集大愛醫生館 deadline 由 6/10（三）09:40，延後至6/10（三）11:15，再請 Alex Chen方便時幫我確認，謝謝。"
        )
        status = view_latest_task.build_confirm_deadline_extension_status(
            task,
            clipboard_text,
            now_local=datetime(2026, 6, 10, 10, 0, tzinfo=timezone(timedelta(hours=8))),
        )
        self.assertEqual(
            status,
            "Success: Confirm deadline extension checked (6/10（三）11:15).",
        )

    def test_extract_deadline_extension_subtasks(self):
        clipboard_text = (
            "因deadline 已至，我先加時間 做其他事時間是 1時35分\n\n"
            "新聞英文與配音 1時35分\n\n"
            "三集大愛醫生館 deadline 由 6/10（三）09:40，延後至6/10（三）11:15，再請 Alex Chen方便時幫我確認，謝謝。"
        )
        self.assertEqual(
            view_latest_task.extract_deadline_extension_subtasks(clipboard_text),
            [("新聞英文與配音", 95)],
        )

    def test_ingest_deadline_extension_subtasks_adds_child(self):
        tasks = [
            {
                "id": "1",
                "name": "三集大愛醫生館",
                "stages": [
                    {
                        "type": "subs",
                        "deadline": "2026-06-10T01:40:00Z",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                    }
                ],
                "children": [],
            }
        ]
        clipboard_text = (
            "因deadline 已至，我先加時間 做其他事時間是 1時35分\n\n"
            "新聞英文與配音 1時35分\n\n"
            "三集大愛醫生館 deadline 由 6/10（三）09:40，延後至6/10（三）11:15，再請 Alex Chen方便時幫我確認，謝謝。"
        )
        inserted = view_latest_task.ingest_deadline_extension_subtasks(tasks, "1", clipboard_text)
        self.assertEqual(inserted, 1)
        self.assertEqual(
            tasks[0]["children"],
            [
                {
                    "id": "2",
                    "name": "新聞英文與配音",
                    "stages": [{"type": "custom", "workMinutes": 95}],
                    "children": [],
                }
            ],
        )

    def test_ingest_deadline_extension_subtasks_is_idempotent_for_same_message(self):
        tasks = [
            {
                "id": "1",
                "name": "三集大愛醫生館",
                "stages": [
                    {
                        "type": "subs",
                        "deadline": "2026-06-10T01:40:00Z",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                    }
                ],
                "children": [
                    {
                        "id": "2",
                        "name": "新聞英文與配音",
                        "stages": [{"type": "custom", "workMinutes": 95}],
                        "children": [],
                    }
                ],
            }
        ]
        clipboard_text = (
            "因deadline 已至，我先加時間 做其他事時間是 1時35分\n\n"
            "新聞英文與配音 1時35分\n\n"
            "三集大愛醫生館 deadline 由 6/10（三）09:40，延後至6/10（三）11:15，再請 Alex Chen方便時幫我確認，謝謝。"
        )
        inserted = view_latest_task.ingest_deadline_extension_subtasks(tasks, "1", clipboard_text)
        self.assertEqual(inserted, 0)
        self.assertEqual(len(tasks[0]["children"]), 1)

    def test_parse_next_task_clipboard_payload_plain_name(self):
        assignee, name = view_latest_task.parse_next_task_clipboard_payload("Alex | 新任務")
        self.assertIsNone(assignee)
        self.assertEqual(name, "Alex | 新任務")

    def test_parse_next_task_clipboard_payload_extracts_name_from_subs_block(self):
        clipboard_text = """請
Alex Chen 翻譯人文講堂 (人文講堂 親密搶奪：人性與法律的修煉 - 李永然) 6 個短版, 長度21分, 預計翻譯16時48分, deadline等手上工作完成再給

親密搶奪：人性與法律的修煉 - 李永然20260110
https://www.youtube.com/watch?v=C3gAhSDUe78
"""
        assignee, name = view_latest_task.parse_next_task_clipboard_payload(clipboard_text)
        self.assertIsNone(assignee)
        self.assertEqual(name, "人文講堂 (人文講堂 親密搶奪：人性與法律的修煉 - 李永然) 6 個短版")

    def test_parse_next_task_clipboard_payload_uses_program_selection_title(self):
        clipboard_text = """請
Alex Chen 翻譯以下節目部選的大愛學漢醫，片長12分，預計做9小時36分，謝謝：

【大愛學漢醫】 排氣不停 中醫有解 - 20221201
https://www.youtube.com/watch?v=DonrkiEXESs
"""
        assignee, name = view_latest_task.parse_next_task_clipboard_payload(clipboard_text)
        self.assertIsNone(assignee)
        self.assertEqual(name, "大愛學漢醫 (排氣不停 中醫有解)")

    def test_parse_next_task_clipboard_payload_strips_program_selection_pipe_metadata(self):
        clipboard_text = """請
Alex Chen 翻譯以下節目部選的大愛學漢醫，片長12分，預計做9小時36分，謝謝：

【大愛學漢醫】 吃出肺活力 — 肺癌照護 | 莊佳穎 | 大愛學漢醫 | 20220823
https://www.youtube.com/watch?v=example
"""
        assignee, name = view_latest_task.parse_next_task_clipboard_payload(clipboard_text)
        self.assertIsNone(assignee)
        self.assertEqual(name, "大愛學漢醫 (吃出肺活力 — 肺癌照護)")

    def test_parse_next_task_clipboard_payload_strips_program_selection_prefix(self):
        assignee, name = view_latest_task.parse_next_task_clipboard_payload(
            "請 Alex Chen 翻譯以下節目部選的大愛學漢醫，片長12分，預計做9小時36分，謝謝："
        )
        self.assertIsNone(assignee)
        self.assertEqual(name, "大愛學漢醫")

    def test_choose_numbered_option_esc_cancels(self):
        with mock.patch("view_latest_task.os.read", return_value=b"\x1b"):
            pick_idx, pick_err, should_quit = view_latest_task.choose_numbered_option(
                stdin_fd=0,
                render_once_fn=lambda status="": "",
                title="Pick",
                options=[("a", "A"), ("b", "B")],
                invalid_selection_msg="bad",
            )
        self.assertIsNone(pick_idx)
        self.assertIsNone(pick_err)
        self.assertFalse(should_quit)

    def test_choose_numbered_option_q_requests_quit(self):
        with mock.patch("view_latest_task.os.read", return_value=b"q"):
            pick_idx, pick_err, should_quit = view_latest_task.choose_numbered_option(
                stdin_fd=0,
                render_once_fn=lambda status="": "",
                title="Pick",
                options=[("a", "A"), ("b", "B")],
                invalid_selection_msg="bad",
            )
        self.assertIsNone(pick_idx)
        self.assertIsNone(pick_err)
        self.assertTrue(should_quit)


if __name__ == "__main__":
    unittest.main()
