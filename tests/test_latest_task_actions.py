import unittest
from unittest import mock

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

    def test_build_message_target_options(self):
        self.assertEqual(
            view_latest_task.build_message_target_options(),
            [
                ("deadline-extension", "Deadline extension message"),
                ("next-task", "Task completion message"),
            ],
        )

    def test_stage_accessors_use_active_stage(self):
        task = {
            "name": "Parent",
            "stages": [
                {
                    "type": "translate",
                    "assignedTo": "Alex",
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

    def test_build_next_task_message_command(self):
        cmd = view_latest_task.build_next_task_message_command("/tmp", "/tmp/tasks.json", "9", "new task", "Alex")
        self.assertEqual(
            cmd,
            [
                "python3",
                "/tmp/create_message.py",
                "-i",
                "/tmp/tasks.json",
                "--type",
                "next-task",
                "--task-id",
                "9",
                "--next-task-name",
                "new task",
                "--next-assignee",
                "Alex",
            ],
        )

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
