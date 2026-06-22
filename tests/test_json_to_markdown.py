import unittest

import json_to_markdown


class JsonToMarkdownTests(unittest.TestCase):
    def test_extension_deadline_is_created_plus_rounded_work(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "stages": [
                    {
                        "startAt": "2026-05-06T05:49:00Z",
                        "deadline": "2026-05-08T08:19:00Z",
                        "workMinutes": 1110,
                        "extensions": [
                            {
                                "name": "Child",
                                "startAt": "2026-05-09T12:21:00Z",
                                "workMinutes": 134,
                            }
                        ]
                    }
                ],
            }
        ]

        md = json_to_markdown.render(tasks, factor=0.8, limit=0)
        self.assertIn("- Work time: 2h 10m", md)
        self.assertIn("- Start: 2026-05-11 Mon 08:00", md)
        self.assertIn("- Deadline: 2026-05-11 Mon 10:10", md)

    def test_extended_deadline_uses_rounded_extension_minutes(self):
        tasks = [
            {
                "id": "1",
                "name": "Parent",
                "stages": [
                    {
                        "startAt": "2026-05-06T05:49:00Z",
                        "deadline": "2026-05-08T08:19:00Z",
                        "workMinutes": 1110,
                        "extensions": [
                            {
                                "name": "Child A",
                                "startAt": "2026-05-09T12:21:00Z",
                                "workMinutes": 134,
                            }
                        ]
                    }
                ],
            }
        ]

        md = json_to_markdown.render(tasks, factor=0.8, limit=0)
        self.assertIn("- Extended deadline: 2026-05-11 Mon 09:29", md)


if __name__ == "__main__":
    unittest.main()
