import unittest

import text_to_json
from task_stages import get_task_content_seconds, get_task_type, get_task_work_minutes, normalize_stages


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
        self.assertEqual(get_task_work_minutes(tasks[0]), 60)
        self.assertEqual(get_task_type(tasks[0]), "posts")
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
        self.assertEqual(get_task_content_seconds(tasks[0]), 110 * 60)
        self.assertEqual(get_task_work_minutes(tasks[0]), 130)
        self.assertEqual(get_task_type(tasks[0]), "news")

    def test_parse_news_accepts_no_space_before_duration(self):
        text = (
            "6/5\n\n"
            "Alex\u00a0Chen: 爾灣人文揚名1:45\n"
            "Emily\u00a0Ding: 鹿野苑首浴佛 1:18\n"
        )
        tasks = text_to_json.parse_news_input(text, 2026, "Alex Chen")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "爾灣人文揚名")
        self.assertEqual(get_task_work_minutes(tasks[0]), 125)
        self.assertEqual(get_task_type(tasks[0]), "news")

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
        self.assertEqual(get_task_content_seconds(task), 1380)
        self.assertEqual(get_task_type(task), "subs")

    def test_subs_program_assignee_uses_mapping_only(self):
        text = (
            "請 Someone 翻譯3集精舍日常(淳師父09 如律如儀) 3 個短版, 長度7分, "
            "預計翻譯5時45分，從4/28（二）16:10起算，deadline為4/29(三) 10:00，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["assignedBy"], "張牧軒")

    def test_subs_program_assignee_preserves_leading_episode_count(self):
        text = (
            "請 Someone 翻譯3集我的阿公阿媽做慈濟, 長度7分, "
            "預計翻譯5時45分，從4/28（二）16:10起算，deadline為4/29(三) 10:00，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["assignedBy"], "Emily")
        self.assertEqual(parsed[0]["name"], "3集我的阿公阿媽做慈濟")

    def test_parse_source_text_subs_accepts_total_content_duration(self):
        text = (
            "接下來請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，片長合計9分，"
            "預計做7 時 12 分，從6/2（二）13:30起算，deadline 為 6/3（三）11:45，謝謝 ~"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        self.assertEqual(task["assignedBy"], "Emily")
        self.assertEqual(get_task_content_seconds(task), 540)
        self.assertEqual(get_task_work_minutes(task), 432)
        self.assertEqual(normalize_stages(task)[0]["deadline"], "2026-06-03T03:45:00Z")

    def test_parse_source_text_subs_alt_format(self):
        text = (
            "張牧軒接下來請翻譯三集精舍日常(怡師父03叢林作息。自我修正、怡師父04－新手典座。資深傳承、"
            "怡師父05種菜修行。種希望 )，片長10分29秒，預計做8小時24分，由5/18（一）08:36起算，"
            "deadline為5/19(二) 9:00，謝謝。"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(get_task_type(task), "subs")
        self.assertEqual(task["assignedBy"], "張牧軒")
        self.assertEqual(get_task_work_minutes(task), 504)
        self.assertEqual(get_task_content_seconds(task), 629)

    def test_parse_source_text_subs_hour_only_with_day_note(self):
        text = (
            "請 Alex Chen 翻譯人文講堂 (送一份專業的禮物 職涯發光 - 方植永) 6 個短版, 長度20分, "
            "預計做16時(2天), 從5/28（四）11:40起算，deadline 6/1(一)11:40，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(get_task_type(task), "subs")
        self.assertEqual(task["assignedBy"], "Evelyn")
        self.assertEqual(get_task_work_minutes(task), 960)
        self.assertIn("6 個短版", task["name"])

    def test_parse_source_text_subs_uses_pm_deadline_when_pm_differs(self):
        text = (
            "翻譯人文講堂 (送一份專業的禮物 職涯發光 - 方植永) 6 個短版, 長度20分, "
            "預計做16時(2天), 從5/28（四）11:40起算，deadline 6/1(一)10:40，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        self.assertEqual(normalize_stages(task)[0]["deadline"], "2026-06-01T02:40:00Z")
        self.assertEqual(
            task.get("__warning__", ""),
            "Warning: PM deadline differs; keeping PM deadline (PM: 2026-06-01 Mon 10:40, computed: 2026-06-01 Mon 11:40).",
        )

    def test_parse_source_text_custom_minutes_format(self):
        parsed = text_to_json.parse_source_text(
            "開會 50分",
            [{"id": "1", "name": "root", "children": []}],
            2026,
        )
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(task["id"], "2")
        self.assertEqual(get_task_type(task), "custom")
        self.assertEqual(task["name"], "開會")
        self.assertEqual(get_task_work_minutes(task), 50)

    def test_parse_source_text_custom_hours_minutes_format(self):
        parsed = text_to_json.parse_source_text(
            "開會 1時20分",
            [{"id": "1", "name": "root", "children": []}],
            2026,
        )
        self.assertEqual(len(parsed), 1)
        task = parsed[0]
        self.assertEqual(get_task_type(task), "custom")
        self.assertEqual(task["name"], "開會")
        self.assertEqual(get_task_work_minutes(task), 80)

    def test_apply_child_work_rule_adjusts_inserted_child_minutes(self):
        task = {
            "id": "3",
            "name": "child",
            "stages": [{"workMinutes": 60}],
            "children": [],
        }
        text_to_json.apply_child_work_rule(task)
        self.assertEqual(get_task_work_minutes(task), 50)

    def test_news_1h45_stores_1h40_after_bonus_and_factor(self):
        parsed = text_to_json.parse_source_text("Alex Chen: 測試新聞 1:45", [], 2026)
        task = parsed[0]
        text_to_json.apply_child_work_rule(task)
        self.assertEqual(get_task_work_minutes(task), 100)

    def test_parse_notes_input_bullet_list(self):
        text = (
            '• "上肢" referred to arms rather than upper body.\n'
            '• "軟" referred to physical weakness/instability rather than tiredness.\n'
        )
        notes = text_to_json.parse_notes_input(text)
        self.assertEqual(
            notes,
            [
                '"上肢" referred to arms rather than upper body.',
                '"軟" referred to physical weakness/instability rather than tiredness.',
            ],
        )

    def test_append_notes_under_parent(self):
        tasks = [
            {"id": "1", "name": "A", "children": []},
            {"id": "2", "name": "B", "children": []},
        ]
        inserted = text_to_json.append_notes_under_parent(tasks, "2", ["note 1", "note 2"])
        self.assertTrue(inserted)
        self.assertEqual(tasks[1]["notes"], ["note 1", "note 2"])

    def test_normalize_task_shape_moves_assigned_to_into_stages(self):
        task = {
            "id": "1",
            "name": "Parent",
            "assignedBy": "Evelyn",
            "assignedTo": "Alex",
            "children": [],
        }
        normalized = text_to_json.normalize_task_shape(task)
        self.assertEqual(normalized["assignedBy"], "Evelyn")
        self.assertEqual(normalized["stages"], [{"assignedTo": "Alex"}])

    def test_normalize_task_shape_moves_flat_fields_into_stages(self):
        task = {
            "id": "1",
            "name": "Parent",
            "type": "subs",
            "assignedTo": "Alex",
            "startAt": "2026-06-02T05:40:00Z",
            "deadline": "2026-06-03T03:40:00Z",
            "workMinutes": 960,
            "contentSeconds": 1200,
            "children": [],
        }
        normalized = text_to_json.normalize_task_shape(task)
        self.assertNotIn("type", normalized)
        self.assertNotIn("assignedTo", normalized)
        self.assertNotIn("startAt", normalized)
        self.assertNotIn("deadline", normalized)
        self.assertNotIn("workMinutes", normalized)
        self.assertNotIn("contentSeconds", normalized)
        self.assertEqual(
            normalized["stages"],
            [
                {
                    "type": "subs",
                    "assignedTo": "Alex",
                    "startAt": "2026-06-02T05:40:00Z",
                    "deadline": "2026-06-03T03:40:00Z",
                    "workMinutes": 960,
                    "contentSeconds": 1200,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
