import unittest

import create_message as cm


class CreateMessageTests(unittest.TestCase):
    def test_deadline_extension_message_defaults_to_latest_task(self):
        tasks = [
            {
                "id": "1",
                "name": "Old task",
                "createdAt": "2026-05-01T00:00:00Z",
                "deadline": "2026-05-02T00:00:00Z",
                "workMinutes": 60,
                "children": [],
            },
            {
                "id": "2",
                "name": "人文講堂 (個人品牌的密碼 - 丁菱娟) 4 個短版",
                "assignedBy": "Evelyn",
                "createdAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [
                    {"id": "3", "name": "英文新聞+錄音", "workMinutes": 130, "children": []},
                    {"id": "4", "name": "小編文", "workMinutes": 60, "children": []},
                ],
            },
        ]

        message = cm.create_message(tasks, msg_type="deadline-extension")
        self.assertEqual(
            message,
            "今日做其他事時間是 2時30分\n\n"
            "英文新聞+錄音 1時40分\n"
            "小編文 50分\n\n"
            "人文講堂 (個人品牌的密碼 - 丁菱娟) 4 個短版，deadline由5/15（五）10:16，延後至5/15（五）13:46，請Evelyn幫我確認，謝謝。",
        )

    def test_deadline_extension_requires_subtasks(self):
        tasks = [
            {
                "id": "1",
                "name": "Only task",
                "assignedBy": "Evelyn",
                "createdAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [],
            }
        ]

        with self.assertRaises(ValueError):
            cm.create_message(tasks, msg_type="deadline-extension")

    def test_deadline_extension_message_uses_0_8_factor(self):
        tasks = [
            {
                "id": "1",
                "name": "Task",
                "assignedBy": "Evelyn",
                "createdAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [
                    {"id": "3", "name": "英文新聞+錄音", "workMinutes": 120, "children": []},
                ],
            }
        ]

        message = cm.create_message(tasks, msg_type="deadline-extension")
        self.assertIn("今日做其他事時間是 1時40分", message)


if __name__ == "__main__":
    unittest.main()
