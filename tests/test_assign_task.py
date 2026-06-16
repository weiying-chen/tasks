import unittest

import assign_task


class AssignTaskTests(unittest.TestCase):
    def test_assign_task_sets_work_minutes_from_content_seconds(self):
        tasks = [
            {
                "id": "1",
                "name": "3集我的阿公阿媽做慈濟",
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "type": "subs",
                        "contentSeconds": 364,
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
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 222,
                        "contentSeconds": 364,
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
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "type": "subs",
                        "startAt": "2026-06-02T01:00:00Z",
                        "deadline": "2026-06-02T05:00:00Z",
                        "workMinutes": 240,
                        "contentSeconds": 600,
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
        self.assertEqual(stage["stage"], "translate")
        self.assertNotIn("status", stage)

    def test_assign_edit_task_updates_matching_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛真健康",
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 180,
                        "contentSeconds": 480,
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
        self.assertEqual(stage["stage"], "edit")
        self.assertNotIn("status", stage)

    def test_assign_edit_task_sets_half_of_translate_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛真健康",
                "assigner": "Emily Ding",
                "stages": [
                    {
                        "type": "subs",
                        "stage": "translate",
                        "assignee": "Emily Ding",
                        "workMinutes": 240,
                        "contentSeconds": 480,
                    },
                    {
                        "type": "subs",
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
        self.assertEqual(stage["stage"], "edit")
        self.assertEqual(stage["workMinutes"], 120)

    def test_assign_task_matches_short_program_name_to_full_task_name(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（杯弓蛇影 乳房腫瘤 + 鬼門關走一遭~冠心病 + 住輸尿管）",
                "assigner": "Alex Chen",
                "stages": [
                    {
                        "type": "subs",
                        "workMinutes": 333,
                        "contentSeconds": 333,
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
        self.assertEqual(stage["stage"], "edit")
        self.assertNotIn("status", stage)

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


if __name__ == "__main__":
    unittest.main()
