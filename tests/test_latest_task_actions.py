import unittest

import view_latest_task as ltv


class LatestTaskActionsTests(unittest.TestCase):
    def test_copy_success_status_messages(self):
        self.assertEqual(
            ltv.DEADLINE_MESSAGE_COPIED_STATUS,
            "Success: Deadline extension message copied to clipboard",
        )
        self.assertEqual(
            ltv.NEXT_TASK_MESSAGE_COPIED_STATUS,
            "Success: Next task message copied to clipboard",
        )

    def test_find_latest_task_id(self):
        tasks = [
            {"id": "1", "name": "A", "children": []},
            {"id": "7", "name": "B", "children": []},
        ]
        self.assertEqual(ltv.find_latest_task_id(tasks), "7")

    def test_build_add_to_latest_command(self):
        cmd = ltv.build_add_to_latest_command("/tmp", "9")
        self.assertEqual(
            cmd,
            ["python3", "/tmp/text_to_json.py", "--parent-id", "9", "__CLIPBOARD__"],
        )

    def test_build_deadline_message_command(self):
        cmd = ltv.build_deadline_message_command("/tmp", "/tmp/tasks.json", "9")
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
        cmd = ltv.build_next_task_message_command("/tmp", "/tmp/tasks.json", "9", "new task", "Alex")
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
        assignee, name = ltv.parse_next_task_clipboard_payload("Alex | 新任務")
        self.assertEqual(assignee, "Alex")
        self.assertEqual(name, "新任務")


if __name__ == "__main__":
    unittest.main()
