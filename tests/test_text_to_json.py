import unittest

from subs_assigners import SUBS_PROGRAM_ASSIGNERS
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
        self.assertNotIn("assigner", tasks[0])

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
        self.assertEqual(get_task_content_seconds(tasks[0]), 105 * 60)
        self.assertEqual(get_task_work_minutes(tasks[0]), 125)
        self.assertEqual(get_task_type(tasks[0]), "news")

    def test_parse_news_accepts_trailing_parenthetical_note(self):
        text = (
            "6/19\n\n"
            "Alex Chen: 賴索托冬令 2:11 (請寫完小編文再開始做)\n"
        )
        tasks = text_to_json.parse_news_input(text, 2026, "Alex Chen")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["name"], "賴索托冬令")
        self.assertEqual(get_task_content_seconds(tasks[0]), 131 * 60)
        self.assertEqual(get_task_work_minutes(tasks[0]), 151)
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
        self.assertEqual(task["assigner"], "Evelyn")
        self.assertEqual(get_task_content_seconds(task), 1380)
        self.assertEqual(get_task_type(task), "subs")

    def test_subs_program_assigner_uses_mapping_only(self):
        text = (
            "請 Someone 翻譯3集精舍日常(淳師父09 如律如儀) 3 個短版, 長度7分, "
            "預計翻譯5時45分，從4/28（二）16:10起算，deadline為4/29(三) 10:00，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["assigner"], "張牧軒 Shawn")

    def test_subs_program_assigner_maps_daily_news_to_elijah(self):
        text = (
            "請 Someone 翻譯3集日日有新知（今天也要學新知），片長10分，"
            "預計做1時，從6/18（四）08:41起算，deadline為6/18（四）09:41，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["assigner"], "Elijah Salie")

    def test_subs_program_assigner_preserves_leading_episode_count(self):
        text = (
            "請 Someone 翻譯3集我的阿公阿媽做慈濟, 長度7分, "
            "預計翻譯5時45分，從4/28（二）16:10起算，deadline為4/29(三) 10:00，謝謝！"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["assigner"], "Emily Ding")
        self.assertEqual(parsed[0]["name"], "3集我的阿公阿媽做慈濟")

    def test_parse_source_text_subs_accepts_total_content_duration(self):
        text = (
            "接下來請 Alex Chen 翻譯3集我的阿公阿媽做慈濟，片長合計9分，"
            "預計做7 時 12 分，從6/2（二）13:30起算，deadline 為 6/3（三）11:45，謝謝 ~"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        self.assertEqual(task["assigner"], "Emily Ding")
        self.assertEqual(get_task_content_seconds(task), 540)
        self.assertEqual(get_task_work_minutes(task), 432)
        self.assertEqual(normalize_stages(task)[0]["deadline"], "2026-06-03T03:45:00Z")

    def test_parse_source_text_subs_accepts_minutes_suffix_and_start_alias(self):
        text = (
            "請 Alex Chen 翻譯3集日日有新知，預計做7小時12分鐘，"
            "從6/18(四) 08:41開始算，deadline為6/18 (四)16:53，謝謝~"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        self.assertEqual(task["assigner"], "Elijah Salie")
        self.assertEqual(get_task_work_minutes(task), 432)
        self.assertEqual(normalize_stages(task)[0]["startAt"], "2026-06-18T00:41:00Z")
        self.assertEqual(normalize_stages(task)[0]["deadline"], "2026-06-18T08:53:00Z")

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
        self.assertEqual(task["assigner"], "張牧軒 Shawn")
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
        self.assertEqual(task["assigner"], "Evelyn")
        self.assertEqual(get_task_work_minutes(task), 960)
        self.assertIn("6 個短版", task["name"])

    def test_parse_source_text_subs_uses_program_selection_title(self):
        text = (
            "請\n"
            "Alex Chen 翻譯以下節目部選的大愛學漢醫，片長12分，預計做9小時36分，謝謝：\n\n"
            "【大愛學漢醫】 排氣不停 中醫有解 - 20221201\n"
            "https://www.youtube.com/watch?v=DonrkiEXESs"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        self.assertEqual(task["name"], "大愛學漢醫 (排氣不停 中醫有解)")
        self.assertEqual(task["assigner"], "Syharn Shen")
        self.assertEqual(get_task_work_minutes(task), 576)
        self.assertEqual(get_task_content_seconds(task), 720)
        self.assertNotIn("deadline", normalize_stages(task)[0])

    def test_parse_source_text_subs_strips_program_selection_pipe_metadata(self):
        text = (
            "請\n"
            "Alex Chen 翻譯以下節目部選的大愛學漢醫，片長12分，預計做9小時36分，謝謝：\n\n"
            "【大愛學漢醫】 吃出肺活力 — 肺癌照護 | 莊佳穎 | 大愛學漢醫 | 20220823\n"
            "https://www.youtube.com/watch?v=example"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["name"], "大愛學漢醫 (吃出肺活力 — 肺癌照護)")

    def test_parse_source_text_subs_strips_program_selection_prefix_without_title_line(self):
        text = "請 Alex Chen 翻譯以下節目部選的大愛學漢醫，片長12分，預計做9小時36分，謝謝："
        parsed = text_to_json.parse_source_text(text, [], 2026)
        self.assertEqual(parsed[0]["name"], "大愛學漢醫")
        self.assertEqual(parsed[0]["assigner"], "Syharn Shen")

    def test_parse_source_text_subs_accepts_spaced_weekday_parentheses(self):
        text = (
            "請\n"
            "Alex Chen 翻譯大愛學漢醫 (排氣不停 中醫有解)，片長12分，預計做9小時36分，"
            "從6/8 (一) 14:43起算，deadline為6/9 (二) 16:20 ，謝謝~"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        stage = normalize_stages(parsed[0])[0]
        self.assertEqual(stage["startAt"], "2026-06-08T06:43:00Z")
        self.assertEqual(stage["deadline"], "2026-06-09T08:20:00Z")

    def test_parse_source_text_subs_supports_tzu_chi_story_mapping(self):
        text = (
            "Alex Chen接下來請Alex翻譯 慈濟的故事(臺北的第二個家 、感念臺北因緣 、講藥師經結緣)，"
            "長24分48秒，預計做19小時51分，由6/12（五）15:00起算，deadline為6/17(三) 9:51，謝謝。"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        stage = normalize_stages(task)[0]
        self.assertEqual(task["assigner"], "張牧軒 Shawn")
        self.assertEqual(task["name"], "慈濟的故事(臺北的第二個家 、感念臺北因緣 、講藥師經結緣)")
        self.assertEqual(get_task_content_seconds(task), 1488)
        self.assertEqual(get_task_work_minutes(task), 1191)
        self.assertEqual(stage["startAt"], "2026-06-12T07:00:00Z")
        self.assertEqual(stage["deadline"], "2026-06-17T01:51:00Z")

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

    def test_parse_source_text_subs_supports_daai_doctor_owner(self):
        text = (
            "請Emily Ding翻譯三集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），"
            "片長共6分04秒，預計翻譯6時04分，deadline等手上工作完成後再給，謝謝~"
        )
        parsed = text_to_json.parse_source_text(text, [], 2026)
        task = parsed[0]
        self.assertEqual(task["assigner"], "Alex Chen")
        self.assertEqual(
            task["name"],
            "三集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
        )
        self.assertEqual(get_task_content_seconds(task), 364)
        self.assertEqual(get_task_work_minutes(task), 364)
        self.assertNotIn("deadline", normalize_stages(task)[0])

    def test_subs_assigner_is_grouped_by_assigner(self):
        self.assertEqual(
            list(SUBS_PROGRAM_ASSIGNERS.items()),
            [
                ("大愛醫生館", "Alex Chen"),
                ("大愛真健康", "Emily Ding"),
                ("我的阿公阿媽做慈濟", "Emily Ding"),
                ("人文講堂", "Evelyn"),
                ("心靈講座", "Evelyn"),
                ("大愛學漢醫", "Syharn Shen"),
                ("日日有新知", "Elijah Salie"),
                ("集日日有新知", "Elijah Salie"),
                ("慈濟的故事", "張牧軒 Shawn"),
                ("精舍日常", "張牧軒 Shawn"),
            ],
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

    def test_normalize_task_shape_moves_assignee_into_stages(self):
        task = {
            "id": "1",
            "name": "Parent",
            "assigner": "Evelyn",
            "assignee": "Alex",
            "children": [],
        }
        normalized = text_to_json.normalize_task_shape(task)
        self.assertEqual(
            normalized,
            {
                "id": "1",
                "name": "Parent",
                "assigner": "Evelyn",
                "stages": [{"assignee": "Alex"}],
                "children": [],
            },
        )

    def test_normalize_task_shape_moves_flat_fields_into_stages(self):
        task = {
            "id": "1",
            "name": "Parent",
            "type": "subs",
            "assignee": "Alex",
            "startAt": "2026-06-02T05:40:00Z",
            "deadline": "2026-06-03T03:40:00Z",
            "workMinutes": 960,
            "contentSeconds": 1200,
            "children": [],
        }
        normalized = text_to_json.normalize_task_shape(task)
        self.assertNotIn("type", normalized)
        self.assertNotIn("assignee", normalized)
        self.assertNotIn("startAt", normalized)
        self.assertNotIn("deadline", normalized)
        self.assertNotIn("workMinutes", normalized)
        self.assertNotIn("contentSeconds", normalized)
        self.assertEqual(
            normalized["stages"],
            [
                {
                    "type": "subs",
                    "assignee": "Alex",
                    "startAt": "2026-06-02T05:40:00Z",
                    "deadline": "2026-06-03T03:40:00Z",
                    "workMinutes": 960,
                    "contentSeconds": 1200,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
