import unittest

import create_message


class CreateMessageTests(unittest.TestCase):
    def test_deadline_window_local_uses_stored_child_minutes(self):
        task = {
            "id": "1",
            "name": "Task",
            "assignedBy": "Evelyn",
            "deadline": "2026-05-15T02:16:00Z",
            "children": [
                {"id": "3", "name": "英文新聞+錄音", "workMinutes": 120, "children": []},
            ],
        }
        previous, next_deadline = create_message.deadline_window_local(task)
        self.assertEqual(create_message.format_message_date(previous), "5/15（五）10:16")
        self.assertEqual(create_message.format_message_date(next_deadline), "5/15（五）13:16")

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
                    {"id": "3", "type": "news", "name": "任意名稱A", "workMinutes": 130, "children": []},
                    {"id": "4", "type": "posts", "name": "任意名稱B", "workMinutes": 60, "children": []},
                ],
            },
        ]

        message = create_message.create_message(tasks, msg_type="deadline-extension")
        self.assertEqual(
            message,
            "今日做其他事時間是 3時10分\n\n"
            "英文新聞+錄音 2時10分\n"
            "小編文 1時\n\n"
            "人文講堂 (個人品牌的密碼 - 丁菱娟) 4 個短版，deadline由5/15（五）10:16，延後至5/15（五）14:26，請Evelyn幫我確認，謝謝。",
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
            create_message.create_message(tasks, msg_type="deadline-extension")

    def test_deadline_extension_message_uses_stored_child_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "Task",
                "assignedBy": "Evelyn",
                "createdAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [
                    {"id": "3", "type": "news", "name": "任意名稱", "workMinutes": 120, "children": []},
                ],
            }
        ]

        message = create_message.create_message(tasks, msg_type="deadline-extension")
        self.assertIn("今日做其他事時間是 2時", message)

    def test_deadline_extension_falls_back_to_name_when_type_missing(self):
        tasks = [
            {
                "id": "1",
                "name": "Task",
                "assignedBy": "Evelyn",
                "createdAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [
                    {"id": "3", "name": "舊資料名稱", "workMinutes": 60, "children": []},
                ],
            }
        ]
        message = create_message.create_message(tasks, msg_type="deadline-extension")
        self.assertIn("舊資料名稱 1時", message)

    def test_next_task_message_uses_finished_task_and_next_name(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assignedBy": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",  # 10:00 local
                "children": [
                    {"id": "2", "name": "其他事", "workMinutes": 60, "children": []},
                ],
            }
        ]

        message = create_message.create_message(
            tasks,
            msg_type="next-task",
            task_id="1",
            next_task_name="新的任務",
        )
        self.assertEqual(
            message,
            "已完成目前完成任務，接下來會開始翻譯新的任務，再麻煩Evelyn便時幫忙設deadline，"
            "從5/14（四）11:00起算，謝謝。\n=====\n"
            "之前是1分鐘算1小時，現在改成1分鐘算0.8 小時，謝謝。",
        )

    def test_next_task_message_uses_explicit_next_assignee(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assignedBy": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        message = create_message.create_message(
            tasks,
            msg_type="next-task",
            task_id="1",
            next_task_name="新的任務",
            next_assignee="Alex",
        )
        self.assertIn("再麻煩Alex便時幫忙設deadline", message)

    def test_next_task_message_requires_task_id_and_next_name(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assignedBy": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        with self.assertRaises(ValueError):
            create_message.create_message(tasks, msg_type="next-task", next_task_name="新的任務")
        with self.assertRaises(ValueError):
            create_message.create_message(tasks, msg_type="next-task", task_id="1")


if __name__ == "__main__":
    unittest.main()
