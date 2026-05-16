import unittest

import text_to_json


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
        tasks = text_to_json.parse_posts_input(text, "alex")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "無私大愛結好緣")
        self.assertEqual(tasks[0]["workMinutes"], 60)
        self.assertEqual(tasks[0]["type"], "posts")
        self.assertNotIn("assignedBy", tasks[0])

    def test_parse_news_only_keeps_alex_chen(self):
        text = (
            "5/13\n\n"
            "Emily Ding: 美YMCA發食物 1:55\n"
            "Alex Chen: 墨安寧牙義診 1:50\n"
        )
        tasks = text_to_json.parse_news_input(text, 2026, "Alex Chen")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "墨安寧牙義診")
        self.assertEqual(tasks[0]["contentSeconds"], 110 * 60)
        self.assertEqual(tasks[0]["workMinutes"], 130)
        self.assertEqual(tasks[0]["type"], "news")

    def test_parse_source_text_uses_posts_before_subs(self):
        text = (
            "4. alex\n"
            "4/26無私大愛結好緣\n"
            "https://www.daai.tv/master/life-wisdom/P90230241?more=true\n"
        )
        parsed = text_to_json.parse_source_text(text, [{"id": "1", "name": "root", "children": []}], 2026)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["id"], "2")
        self.assertEqual(parsed[0]["name"], "無私大愛結好緣")

    def test_parse_source_text_subs_shape(self):
        text = (
            "請 Anyone 翻譯人文講堂(活出自己的第三人生 - 丁菱娟) 5 個短版, 長度23分, "
            "預計翻譯18時30分(2天2時30分)，從5/6（三）13:49起算，deadline為5/8(五) 16:19，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(task["id"], "1")
        self.assertEqual(task["assignedBy"], "Evelyn")
        self.assertEqual(task["contentSeconds"], 1380)
        self.assertEqual(task["type"], "subs")

    def test_subs_program_assignee_uses_mapping_only(self):
        text = (
            "請 Someone 翻譯3集精舍日常(淳師父09 如律如儀) 3 個短版, 長度7分, "
            "預計翻譯5時45分，從4/28（二）16:10起算，deadline為4/29(三) 10:00，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["assignedBy"], "張牧軒")

    def test_parse_source_text_subs_alt_format(self):
        text = (
            "張牧軒接下來請翻譯三集精舍日常(怡師父03叢林作息。自我修正、怡師父04－新手典座。資深傳承、"
            "怡師父05種菜修行。種希望 )，片長10分29秒，預計做8小時24分，由5/18（一）08:36起算，"
            "deadline為5/19(二) 9:00，謝謝。"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(task["type"], "subs")
        self.assertEqual(task["assignedBy"], "張牧軒")
        self.assertEqual(task["workMinutes"], 504)
        self.assertEqual(task["contentSeconds"], 629)

    def test_parse_source_text_custom_minutes_format(self):
        parsed = text_to_json.parse_source_text(
            "開會 50分",
            [{"id": "1", "name": "root", "children": []}],
            2026,
        )
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(task["id"], "2")
        self.assertEqual(task["type"], "custom")
        self.assertEqual(task["name"], "開會")
        self.assertEqual(task["workMinutes"], 50)

    def test_parse_source_text_custom_hours_minutes_format(self):
        parsed = text_to_json.parse_source_text(
            "開會 1時20分",
            [{"id": "1", "name": "root", "children": []}],
            2026,
        )
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(task["type"], "custom")
        self.assertEqual(task["name"], "開會")
        self.assertEqual(task["workMinutes"], 80)

    def test_apply_child_work_rule_adjusts_inserted_child_minutes(self):
        task = {
            "id": "3",
            "name": "child",
            "workMinutes": 60,
            "children": [],
        }
        text_to_json.apply_child_work_rule(task)
        self.assertEqual(task["workMinutes"], 50)

    def test_news_1h45_stores_1h40_after_bonus_and_factor(self):
        parsed = text_to_json.parse_source_text("Alex Chen: 測試新聞 1:45", [], 2026)
        task = parsed[0]
        text_to_json.apply_child_work_rule(task)
        self.assertEqual(task["workMinutes"], 100)


if __name__ == "__main__":
    unittest.main()
