import unittest

import assign_task


class AssignTaskTests(unittest.TestCase):
    def test_parse_translate_assignment_message(self):
        parsed = assign_task.parse_translate_assignment_message(
            "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~"
        )
        self.assertEqual(
            parsed,
            {
                "assignedBy": "Emily Ding",
                "assignedTo": "Alex Chen",
                "name": "3集我的阿公阿媽做慈濟",
            },
        )

    def test_assign_translate_task_updates_matching_stage(self):
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
        updated = assign_task.assign_translate_task(
            tasks,
            "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~",
        )
        stage = updated[0]["stages"][0]
        self.assertEqual(updated[0]["assignedBy"], "Emily Ding")
        self.assertEqual(stage["assignedTo"], "Alex Chen")
        self.assertEqual(stage["status"], "assigned")

    def test_assign_translate_task_errors_when_no_match(self):
        tasks = [
            {
                "id": "1",
                "name": "別的任務",
                "stages": [{"type": "subs", "status": "queued"}],
                "children": [],
            }
        ]
        with self.assertRaisesRegex(ValueError, "No matching top-level task"):
            assign_task.assign_translate_task(
                tasks,
                "Emily Ding 請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，謝謝~",
            )


if __name__ == "__main__":
    unittest.main()
