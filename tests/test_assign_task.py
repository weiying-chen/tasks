import unittest

import assign_task


class AssignTaskTests(unittest.TestCase):
    def test_parse_translate_assignment_message(self):
        parsed = assign_task.parse_assignment_message(
            "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~"
        )
        self.assertEqual(
            parsed,
            {
                "assignedBy": "Emily Ding",
                "assignedTo": "Alex Chen",
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
                "assignedBy": "Evelyn",
                "assignedTo": "Alex Chen",
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
                "assignedBy": "Emily Ding",
                "assignedTo": "Alex Chen",
                "stage": "edit",
                "name": "3集大愛真健康",
            },
        )

    def test_assign_task_updates_matching_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集我的阿公阿媽做慈濟",
                "assignedBy": "Emily",
                "stages": [
                    {
                        "type": "subs",
                        "status": "queued",
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
        self.assertEqual(updated[0]["assignedBy"], "Emily Ding")
        self.assertEqual(stage["assignedTo"], "Alex Chen")
        self.assertEqual(stage["stage"], "translate")
        self.assertEqual(stage["status"], "assigned")

    def test_assign_edit_task_updates_matching_stage(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛真健康",
                "assignedBy": "Emily",
                "stages": [
                    {
                        "type": "subs",
                        "status": "queued",
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
        self.assertEqual(updated[0]["assignedBy"], "Emily Ding")
        self.assertEqual(stage["assignedTo"], "Alex Chen")
        self.assertEqual(stage["stage"], "edit")
        self.assertEqual(stage["status"], "assigned")

    def test_assign_task_matches_short_program_name_to_full_task_name(self):
        tasks = [
            {
                "id": "1",
                "name": "3集大愛醫生館（杯弓蛇影 乳房腫瘤 + 鬼門關走一遭~冠心病 + 住輸尿管）",
                "assignedBy": "Alex Chen",
                "stages": [
                    {
                        "type": "subs",
                        "status": "queued",
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
        self.assertEqual(stage["assignedTo"], "張牧軒 Shawn")
        self.assertEqual(stage["stage"], "edit")
        self.assertEqual(stage["status"], "assigned")

    def test_assign_task_errors_when_no_match(self):
        tasks = [
            {
                "id": "1",
                "name": "別的任務",
                "stages": [{"type": "subs", "status": "queued"}],
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
