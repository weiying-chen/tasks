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

    def test_next_task_message_uses_previous_final_deadline(self):
        tasks = [
            {
                "id": "1",
                "name": "前一個任務",
                "assignedBy": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",  # 10:00 local
                "children": [
                    {"id": "2", "name": "其他事", "workMinutes": 60, "children": []},  # 50m after 0.8+round
                ],
            },
            {
                "id": "3",
                "name": "下一個任務",
                "assignedBy": "Evelyn",
                "deadline": "2026-05-15T02:16:00Z",
                "children": [],
            },
        ]

        message = cm.create_message(tasks, msg_type="next-task")
        self.assertEqual(
            message,
            "已完成前一個任務，接下來會開始翻譯下一個任務，再麻煩Evelyn便時幫忙設deadline，"
            "從5/14（四）10:50起算，謝謝。\n=====\n"
            "之前是1分鐘算1小時，現在改成1分鐘算0.8 小時，謝謝。",
        )


if __name__ == "__main__":
    unittest.main()
