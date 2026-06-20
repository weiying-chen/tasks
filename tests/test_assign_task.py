import unittest

import assign_task


class AssignTaskTests(unittest.TestCase):
    def test_assign_task_sets_work_minutes_from_content_seconds(self):
        tasks = [
            {
                "id": "1",
                "name": "3集我的阿公阿媽做慈濟",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Emily Ding",
                "stages": [
                    {
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "Emily Ding 請 Emily Ding 翻譯3集我的阿公阿媽做慈濟，謝謝~",
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(stage["workMinutes"], 364)

    def test_assignee_work_rate_uses_full_name(self):
        self.assertIn("Emily Ding", assign_task.TRANSLATION_WORK_RATE_BY_ASSIGNEE)
        self.assertNotIn("Emily", assign_task.TRANSLATION_WORK_RATE_BY_ASSIGNEE)
        self.assertEqual(assign_task.get_assignee_work_rate("Emily Ding"), 1.0)

    def test_assign_task_keeps_existing_work_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "3集我的阿公阿媽做慈濟",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "workMinutes": 222,
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "Emily Ding 請 Emily Ding 翻譯3集我的阿公阿媽做慈濟，謝謝~",
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(stage["workMinutes"], 222)

    def test_parse_translate_assignment_message(self):
        parsed = assign_task.parse_assignment_message(
            "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~"
        )
        self.assertEqual(
            parsed,
            {
                "assigner": "Emily Ding",
                "assignee": "Alex Chen",
                "stage": "translate",
                "name": "3集我的阿公阿媽做慈濟",
            },
        )

    def test_parse_translate_assignment_message_with_punctuation_noise(self):
        parsed = assign_task.parse_assignment_message(
            "Evelyn .請 Alex Chen 翻譯人文講堂 (人文講堂 親密搶奪：人性與法律的修煉 - 李永然 6)，謝謝~"
        )
        self.assertEqual(
            parsed,
            {
                "assigner": "Evelyn",
                "assignee": "Alex Chen",
                "stage": "translate",
                "name": "人文講堂 (人文講堂 親密搶奪：人性與法律的修煉 - 李永然 6)",
            },
        )

    def test_parse_edit_assignment_message_with_give_me_variant(self):
        parsed = assign_task.parse_assignment_message(
            "請\nEmily Ding 給我 edit + 定稿3集大愛真健康，謝謝~"
        )
        self.assertEqual(
            parsed,
            {
                "assigner": "Emily Ding",
                "assignee": "Alex Chen",
                "stage": "edit",
                "name": "3集大愛真健康",
            },
        )

    def test_assign_task_updates_matching_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集我的阿公阿媽做慈濟",
                "type": "subs",
                "contentSeconds": 600,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "startAt": "2026-06-02T01:00:00Z",
                        "deadline": "2026-06-02T05:00:00Z",
                        "workMinutes": 240,
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~",
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(updated[0]["assigner"], "Emily Ding")
        self.assertEqual(stage["assignee"], "Alex Chen")
        self.assertEqual(stage["name"], "translate")
        self.assertNotIn("status", stage)

    def test_assign_edit_task_updates_matching_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛真健康",
                "type": "subs",
                "contentSeconds": 480,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "workMinutes": 180,
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "請\nEmily Ding 給我 edit + 定稿3集大愛真健康，謝謝~",
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(updated[0]["assigner"], "Emily Ding")
        self.assertEqual(stage["assignee"], "Alex Chen")
        self.assertEqual(stage["name"], "edit")
        self.assertNotIn("status", stage)

    def test_assign_edit_task_sets_half_of_translate_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛真健康",
                "type": "subs",
                "contentSeconds": 480,
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "stage": "translate",
                        "assignee": "Emily Ding",
                        "workMinutes": 240,
                    },
                    {
                    },
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "請\nEmily Ding 給我 edit + 定稿3集大愛真健康，謝謝~",
        )
        stage = updated[0]["stages"][1]
        self.assertEqual(stage["assignee"], "Alex Chen")
        self.assertEqual(stage["name"], "edit")
        self.assertEqual(stage["workMinutes"], 120)

    def test_assign_task_matches_short_program_name_to_full_task_name(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（杯弓蛇影 乳房腫瘤 + 鬼門關走一遭~冠心病 + 住輸尿管）",
                "type": "subs",
                "contentSeconds": 333,
                "assigner": "Alex Chen",
                "stages": [
                    {
                        "workMinutes": 333,
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "Alex Chen 請 張牧軒 Shawn edit+定稿 3 集大愛醫生館，謝謝~",
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(stage["assignee"], "張牧軒 Shawn")
        self.assertEqual(stage["name"], "edit")
        self.assertNotIn("status", stage)

    def test_assign_edit_task_appends_new_stage_after_translate_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "type": "subs",
                "contentSeconds": 364,
                "assigner": "Alex Chen",
                "stages": [
                    {
                        "name": "translate",
                        "assignee": "Emily Ding",
                        "startAt": "2026-06-09T03:35:00Z",
                        "deadline": "2026-06-10T01:40:00Z",
                        "workMinutes": 364,
                        "extensions": [
                            {
                                "name": "新聞英文與配音",
                                "type": "custom",
                                "workMinutes": 95,
                            }
                        ],
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.assign_task(
            tasks,
            "Alex Chen 請 張牧軒 Shawn edit+定稿 3 集大愛醫生館，謝謝~",
        )
        self.assertEqual(len(updated[0]["stages"]), 2)
        translate_stage = updated[0]["stages"][0]
        edit_stage = updated[0]["stages"][1]
        self.assertEqual(translate_stage["assignee"], "Emily Ding")
        self.assertEqual(translate_stage["name"], "translate")
        self.assertIn("extensions", translate_stage)
        self.assertEqual(edit_stage["assignee"], "張牧軒 Shawn")
        self.assertEqual(edit_stage["name"], "edit")
        self.assertNotIn("contentSeconds", edit_stage)
        self.assertNotIn("extensions", edit_stage)
        self.assertNotIn("startAt", edit_stage)
        self.assertNotIn("deadline", edit_stage)

    def test_assign_task_does_not_match_partial_prefix_only(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（杯弓蛇影 乳房腫瘤 + 鬼門關走一遭~冠心病 + 住輸尿管）",
                "stages": [{"type": "subs"}],
                "children": [],
            }
        ]
        with self.assertRaisesRegex(ValueError, "No matching top-level task"):
            assign_task.assign_task(
                tasks,
                "Alex Chen 請 張牧軒 Shawn edit+定稿 3 集大愛醫生，謝謝~",
            )

    def test_assign_task_errors_when_no_match(self):
        tasks = [
            {
                "id": "1",
                "name": "別的任務",
                "stages": [{"type": "subs"}],
                "children": [],
            }
        ]
        with self.assertRaisesRegex(ValueError, "No matching top-level task"):
            assign_task.assign_task(
                tasks,
                "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~",
            )

    def test_parse_task_start_message(self):
        parsed = assign_task.parse_task_start_message(
            "已完成翻譯報獎節目，接下來我會開始翻譯大愛醫生館 deadline從6/9 (二) 11:35 起算，再麻煩Alex Chen 方便時幫我設deadline，謝謝。",
            year=2026,
        )
        self.assertEqual(
            parsed,
            {
                "name": "大愛醫生館",
                "startAt": "2026-06-09T03:35:00Z",
            },
        )

    def test_confirm_task_start_sets_start_and_deadline(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                "assigner": "Alex Chen",
                "stages": [
                    {
                        "type": "subs",
                        "stage": "translate",
                        "assignee": "Emily Ding",
                        "workMinutes": 364,
                        "contentSeconds": 364,
                    }
                ],
                "children": [],
            }
        ]
        updated = assign_task.confirm_task_start(
            tasks,
            "已完成翻譯報獎節目，接下來我會開始翻譯大愛醫生館 deadline從6/9 (二) 11:35 起算，再麻煩Alex Chen 方便時幫我設deadline，謝謝。",
            year=2026,
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(stage["startAt"], "2026-06-09T03:35:00Z")
        self.assertEqual(stage["deadline"], "2026-06-10T01:40:00Z")


if __name__ == "__main__":
    unittest.main()
