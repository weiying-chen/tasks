import unittest

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
        cmd = view_latest_task.build_add_to_latest_command("/tmp", "9", "children")
        self.assertEqual(
            cmd,
            ["python3", "/tmp/text_to_json.py", "--parent-id", "9", "--target", "children", "__CLIPBOARD__"],
        )

    def test_build_add_notes_to_latest_command(self):
        cmd = view_latest_task.build_add_to_latest_command("/tmp", "9", "notes")
        self.assertEqual(
            cmd,
            ["python3", "/tmp/text_to_json.py", "--parent-id", "9", "--target", "notes", "__CLIPBOARD__"],
        )

    def test_build_add_task_command(self):
        cmd = view_latest_task.build_add_task_command("/tmp")
        self.assertEqual(cmd, ["/tmp/add_task.sh"])

    def test_build_add_notes_command(self):
        cmd = view_latest_task.build_add_notes_command("/tmp", "9")
        self.assertEqual(
            cmd,
            ["python3", "/tmp/text_to_json.py", "--parent-id", "9", "--target", "notes", "__CLIPBOARD__"],
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

    def test_parse_next_task_clipboard_payload(self):
        assignee, name = view_latest_task.parse_next_task_clipboard_payload("Alex | 新任務")
        self.assertIsNone(assignee)
        self.assertEqual(name, "Alex | 新任務")


if __name__ == "__main__":
    unittest.main()
