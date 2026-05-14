import unittest

import text_to_json as t2j


class TextToJsonTests(unittest.TestCase):
    def test_parse_posts_only_keeps_alex(self):
        text = (
            "1. evelyn\n"
            "4/24大愛醫療永流傳\n"
            "https://example.com/a\n\n"
            "2. alex\n"
            "4/26無私大愛結好緣\n"
            "https://example.com/b\n"
        )
        tasks = t2j.parse_posts_input(text, "alex")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "無私大愛結好緣")
        self.assertEqual(tasks[0]["workMinutes"], 60)
        self.assertNotIn("assignedBy", tasks[0])

    def test_parse_news_only_keeps_alex_chen(self):
        text = (
            "5/13\n\n"
            "Emily Ding: 美YMCA發食物 1:55\n"
            "Alex Chen: 墨安寧牙義診 1:50\n"
        )
        tasks = t2j.parse_news_input(text, 2026, "Alex Chen")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "墨安寧牙義診")
        self.assertEqual(tasks[0]["contentSeconds"], 110 * 60)
        self.assertEqual(tasks[0]["workMinutes"], 130)

    def test_parse_source_text_uses_posts_before_subs(self):
        text = (
            "4. alex\n"
            "4/26無私大愛結好緣\n"
            "https://www.daai.tv/master/life-wisdom/P90230241?more=true\n"
        )
        parsed = t2j.parse_source_text(text, [{"id": "1", "name": "root", "children": []}], 2026)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["id"], "2")
        self.assertEqual(parsed[0]["name"], "無私大愛結好緣")

    def test_parse_source_text_subs_shape(self):
        text = (
            "請 Alex Chen 翻譯人文講堂(活出自己的第三人生 - 丁菱娟) 5 個短版, 長度23分, "
            "預計翻譯18時30分(2天2時30分)，從5/6（三）13:49起算，deadline為5/8(五) 16:19，謝謝！"
        )
        parsed = t2j.parse_source_text(text, [], 2026)
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(task["id"], "1")
        self.assertEqual(task["assignedBy"], "Alex Chen")
        self.assertEqual(task["contentSeconds"], 1380)


if __name__ == "__main__":
    unittest.main()
