import unittest

import json_to_markdown as j2m


class JsonToMarkdownTests(unittest.TestCase):
    def test_child_deadline_is_created_plus_rounded_work(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "createdAt": "2026-05-06T05:49:00Z",
                "deadline": "2026-05-08T08:19:00Z",
                "workMinutes": 1110,
                "children": [
                    {
                        "id": "2",
                        "name": "Child",
                        "createdAt": "2026-05-09T12:21:00Z",
                        "workMinutes": 134,
                        "children": [],
                    }
                ],
            }
        ]

        md = j2m.render(tasks, factor=0.8)
        self.assertIn("- Work time: 2h 10m", md)
        self.assertIn("- Created: 2026-05-11 Mon 08:00", md)
        self.assertIn("- Deadline: 2026-05-11 Mon 10:10", md)

    def test_extended_deadline_uses_rounded_child_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "createdAt": "2026-05-06T05:49:00Z",
                "deadline": "2026-05-08T08:19:00Z",
                "workMinutes": 1110,
                "children": [
                    {
                        "id": "2",
                        "name": "Child A",
                        "createdAt": "2026-05-09T12:21:00Z",
                        "workMinutes": 134,
                        "children": [],
                    }
                ],
            }
        ]

        md = j2m.render(tasks, factor=0.8)
        self.assertIn("- Extended deadline: 2026-05-11 Mon 09:29", md)


if __name__ == "__main__":
    unittest.main()
