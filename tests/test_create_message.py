import unittest
from datetime import datetime, timezone, timedelta

import create_message


class CreateMessageTests(unittest.TestCase):
    def test_format_mention_prefixes_names_once(self):
        self.assertEqual(create_message.format_mention("Evelyn"), "@Evelyn")
        self.assertEqual(create_message.format_mention("@Evelyn"), "@Evelyn")
        self.assertEqual(create_message.format_mention(""), "")

    def test_deadline_window_local_uses_stored_child_minutes(self):
        task = {
            "id": "1",
            "name": "Task",
            "assigner": "Evelyn",
            "deadline": "2026-05-15T02:16:00Z",
            "children": [
                {"id": "3", "name": "英文新聞+錄音", "workMinutes": 120, "children": []},
            ],
        }
        previous, next_deadline = create_message.deadline_window_local(task)
        self.assertEqual(create_message.format_message_date(previous), "5/15（五）10:16")
        self.assertEqual(create_message.format_message_date(next_deadline), "5/15（五）13:16")

    def test_deadline_window_local_falls_back_to_computed_deadline(self):
        task = {
            "id": "11",
            "name": "Task",
            "startAt": "2026-05-26T07:04:00Z",
            "workMinutes": 576,
            "children": [],
        }
        previous, next_deadline = create_message.deadline_window_local(task, child_minutes=0)
        self.assertEqual(create_message.format_message_date(previous), "5/27（三）16:40")
        self.assertEqual(create_message.format_message_date(next_deadline), "5/27（三）16:40")

    def test_deadline_extension_message_defaults_to_latest_task(self):
        tasks = [
            {
                "id": "1",
                "name": "Old task",
                "startAt": "2026-05-01T00:00:00Z",
                "deadline": "2026-05-02T00:00:00Z",
                "workMinutes": 60,
                "children": [],
            },
            {
                "id": "2",
                "name": "人文講堂 (個人品牌的密碼 - 丁菱娟) 4 個短版",
                "assigner": "Evelyn",
                "startAt": "2026-05-13T00:40:00Z",
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
            "人文講堂 (個人品牌的密碼 - 丁菱娟) 4 個短版，deadline由5/15（五）10:16，延後至5/15（五）14:26，請@Evelyn幫我確認，謝謝。",
        )

    def test_deadline_extension_requires_subtasks(self):
        tasks = [
            {
                "id": "1",
                "name": "Only task",
                "assigner": "Evelyn",
                "startAt": "2026-05-13T00:40:00Z",
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
                "assigner": "Evelyn",
                "startAt": "2026-05-13T00:40:00Z",
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
                "assigner": "Evelyn",
                "startAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [
                    {"id": "3", "name": "舊資料名稱", "workMinutes": 60, "children": []},
                ],
            }
        ]
        message = create_message.create_message(tasks, msg_type="deadline-extension")
        self.assertIn("舊資料名稱 1時", message)

    def test_deadline_extension_includes_only_current_workday_children(self):
        tasks = [
            {
                "id": "1",
                "name": "Task",
                "assigner": "Evelyn",
                "startAt": "2026-05-13T00:40:00Z",
                "deadline": "2026-05-15T02:16:00Z",
                "workMinutes": 1056,
                "children": [
                    {
                        "id": "2",
                        "type": "news",
                        "name": "old child",
                        "startAt": "2026-05-25T02:00:00Z",
                        "workMinutes": 60,
                        "children": [],
                    },
                    {
                        "id": "3",
                        "type": "posts",
                        "name": "today child",
                        "startAt": "2026-05-26T01:00:00Z",
                        "workMinutes": 50,
                        "children": [],
                    },
                ],
            }
        ]
        now_local = datetime(2026, 5, 26, 16, 0, tzinfo=timezone(timedelta(hours=8)))
        message = create_message.create_message(tasks, msg_type="deadline-extension", now_local=now_local)
        self.assertIn("今日做其他事時間是 50分", message)
        self.assertIn("小編文 50分", message)
        self.assertNotIn("英文新聞+錄音", message)
        self.assertIn("deadline由5/15（五）11:16", message)
        self.assertIn("延後至5/15（五）13:06", message)

    def test_deadline_extension_uses_prior_subtasks_as_baseline(self):
        tasks = [
            {
                "id": "1",
                "name": "Task",
                "assigner": "Evelyn",
                "deadline": "2026-05-27T08:40:00Z",  # 16:40 local
                "children": [
                    {
                        "id": "2",
                        "type": "news",
                        "name": "yesterday child",
                        "startAt": "2026-05-27T02:00:00Z",
                        "workMinutes": 130,
                        "children": [],
                    },
                    {
                        "id": "3",
                        "type": "news",
                        "name": "today child",
                        "startAt": "2026-05-28T01:00:00Z",
                        "workMinutes": 110,
                        "children": [],
                    },
                ],
            }
        ]
        now_local = datetime(2026, 5, 28, 10, 0, tzinfo=timezone(timedelta(hours=8)))
        message = create_message.create_message(tasks, msg_type="deadline-extension", now_local=now_local)
        self.assertIn("英文新聞+錄音 1時50分", message)
        self.assertIn("deadline由5/28（四）09:50", message)
        self.assertIn("延後至5/28（四）11:40", message)

    def test_next_task_message_uses_finished_task_and_next_name(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assigner": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",  # 10:00 local
                "children": [
                    {"id": "2", "name": "其他事", "workMinutes": 60, "children": []},
                ],
            }
        ]

        message = create_message.create_message(
            tasks,
            msg_type="task-completion",
            task_id="1",
            next_task_name="新的任務",
        )
        self.assertEqual(
            message,
            "已完成目前完成任務，接下來會開始翻譯新的任務，再麻煩@Evelyn便時幫忙設deadline，"
            "從5/14（四）11:00起算，謝謝。",
        )

    def test_next_task_message_uses_explicit_next_assigner(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assigner": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        message = create_message.create_message(
            tasks,
            msg_type="task-completion",
            task_id="1",
            next_task_name="新的任務",
            next_assigner="Alex",
        )
        self.assertIn("再麻煩@Alex便時幫忙設deadline", message)

    def test_next_task_message_prefers_mapping_from_next_task_name(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assigner": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        message = create_message.create_message(
            tasks,
            msg_type="task-completion",
            task_id="1",
            next_task_name="人文講堂（測試）",
        )
        self.assertIn("再麻煩@Evelyn便時幫忙設deadline", message)

    def test_next_task_message_uses_mapping_over_finished_task_owner(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assigner": "Syharn Shen",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        message = create_message.create_message(
            tasks,
            msg_type="task-completion",
            task_id="1",
            next_task_name="精舍日常（測試）",
        )
        self.assertIn("再麻煩@張牧軒 Shawn便時幫忙設deadline", message)

    def test_next_task_message_uses_mapping_for_spiritual_talk(self):
        tasks = [
            {
                "id": "1",
                "name": "3集日日有新知 (如何讓蘋果更耐旱＋現代人都驚嘆的2500年前宇宙觀＋少睡多讀成績好?)",
                "assigner": "Elijah Salie",
                "deadline": "2026-06-18T08:53:00Z",
                "children": [],
            }
        ]
        message = create_message.create_message(
            tasks,
            msg_type="task-completion",
            task_id="1",
            next_task_name="心靈講座(在不確定中走出確定 - 童子賢) 4 個短版",
        )
        self.assertIn("再麻煩@Evelyn便時幫忙設deadline", message)

    def test_next_task_message_uses_mapping_for_citizens_story(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assigner": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        message = create_message.create_message(
            tasks,
            msg_type="task-completion",
            task_id="1",
            next_task_name="慈濟的故事(臺北的第二個家 、感念臺北因緣 、講藥師經結緣 )",
        )
        self.assertIn("再麻煩@張牧軒 Shawn便時幫忙設deadline", message)

    def test_next_task_message_requires_task_id_and_next_name(self):
        tasks = [
            {
                "id": "1",
                "name": "目前完成任務",
                "assigner": "Evelyn",
                "deadline": "2026-05-14T02:00:00Z",
                "children": [],
            }
        ]
        with self.assertRaises(ValueError):
            create_message.create_message(tasks, msg_type="task-completion", next_task_name="新的任務")
        with self.assertRaises(ValueError):
            create_message.create_message(tasks, msg_type="task-completion", task_id="1")

    def test_subs_summary_message_uses_parenthesized_episode_titles(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "assignee": "Shawn",
                        "workMinutes": 364,
                    }
                ],
                "children": [],
            }
        ]

        message = create_message.create_message(tasks, msg_type="task-assignment")
        self.assertEqual(
            message,
            "請@Shawn翻譯3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），"
            "片長共6分04秒，預計翻譯6時04分，deadline等手上工作完成後再給，謝謝~",
        )

    def test_subs_summary_message_uses_edit_wording_for_edit_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "type": "subs",
                "contentSeconds": 333,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "stage": "translate",
                        "assignee": "Emily Ding",
                        "workMinutes": 333,
                    },
                    {
                        "stage": "edit",
                        "assignee": "Shawn",
                        "workMinutes": 166,
                    }
                ],
                "children": [],
            }
        ]

        message = create_message.create_message(tasks, msg_type="task-assignment")
        self.assertEqual(
            message,
            "請@Shawn edit + 定稿3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），"
            "片長共5分33秒，翻譯工時5時33分，預計製作2時46分，deadline等手上工作完成後再給，謝謝~",
        )

    def test_subs_summary_message_omits_deadline_for_elijah(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "stage": "translate",
                        "assignee": "Emily Ding",
                        "workMinutes": 364,
                    },
                    {
                        "stage": "edit",
                        "assignee": "Elijah Salie",
                        "workMinutes": 182,
                    },
                ],
                "children": [],
            }
        ]

        message = create_message.create_message(tasks, msg_type="task-assignment")
        self.assertEqual(
            message,
            "請@Elijah Salie edit + 定稿3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），"
            "片長共6分04秒，翻譯工時6時04分，預計製作3時02分，謝謝~",
        )

    def test_subs_initiation_message_uses_translate_wording(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "stage": "translate",
                        "assignee": "Shawn",
                        "startAt": "2026-06-09T03:35:00Z",
                        "deadline": "2026-06-10T01:40:00Z",
                        "workMinutes": 364,
                    }
                ],
                "children": [],
            }
        ]

        message = create_message.create_message(tasks, msg_type="task-initiation")
        self.assertEqual(
            message,
            "請@Shawn翻譯3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），"
            "片長共6分04秒，預計做6時04分，從6/9（二）11:35起算，deadline 6/10（三）09:40，謝謝！",
        )

    def test_subs_initiation_message_uses_edit_wording(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（杯弓蛇影 乳房腫瘤 + 鬼門關走一遭~冠心病 + 住輸尿管）",
                "type": "subs",
                "contentSeconds": 333,
                "assigner": "Alex Chen",
                "stages": [
                    {
                        "stage": "edit",
                        "assignee": "Shawn",
                        "startAt": "2026-06-02T05:32:00Z",
                        "deadline": "2026-06-02T08:18:00Z",
                        "workMinutes": 166,
                    }
                ],
                "children": [],
            }
        ]

        message = create_message.create_message(tasks, msg_type="task-initiation")
        self.assertEqual(
            message,
            "請@Shawn edit + 定稿3集大愛醫生館（杯弓蛇影 乳房腫瘤 + 鬼門關走一遭~冠心病 + 住輸尿管），"
            "片長共5分33秒，預計製作2時46分，從6/2（二）13:32起算，deadline 6/2（二）16:18，謝謝！",
        )

    def test_subs_summary_message_requires_parenthesized_episode_titles(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "assignee": "Alex Chen",
                        "workMinutes": 364,
                    }
                ],
                "children": [],
            }
        ]

        with self.assertRaises(ValueError):
            create_message.create_message(tasks, msg_type="task-assignment")


if __name__ == "__main__":
    unittest.main()
