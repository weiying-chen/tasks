import json
import unittest
from pathlib import Path


def find_extension_by_name(tasks, name):
    for task in tasks:
        for stage in task.get("stages", []):
            for extension in stage.get("extensions", []):
                if extension.get("name") == name:
                    return extension
    return None


class TasksJsonTests(unittest.TestCase):
    def test_latest_coworker_task_groups_three_daai_doctor_episodes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks_coworkers.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        last_task = tasks[-1]
        self.assertEqual(
            last_task["name"],
            "3集大愛醫生館（聲帶增胖 + 膽結石肆虐胰臟 + 晦暗不明出血點）",
        )
        self.assertEqual(last_task["contentSeconds"], 303)
        self.assertIn("sourceText", last_task)
        self.assertEqual(
            last_task["stages"],
            [
                {
                    "name": "finalize",
                    "assignee": "Elijah Salie",
                    "workMinutes": 242,
                }
            ],
        )

    def test_post_extension_keeps_work_minutes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        extension = find_extension_by_name(tasks, "視病如親暖杏林")

        self.assertIsNotNone(extension)
        self.assertEqual(extension.get("workMinutes"), 50)

    def test_tijuana_environment_news_work_time_is_two_hours(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        extension = find_extension_by_name(tasks, "提娃那社區環保")

        self.assertIsNotNone(extension)
        self.assertEqual(extension.get("workMinutes"), 120)

    def test_chuan_cheng_yi_dao_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        extension = find_extension_by_name(tasks, "傳承醫道暖杏林")

        self.assertIsNotNone(extension)
        self.assertEqual(
            extension.get("notes"),
            [
                "Changed the nurse's story to emphasize passing on the care she received (\"extend that same care to others\") rather than only becoming a nurse.",
                "Changed the Master's encouragement from \"professionalism\" to \"expertise\" to better fit the medical context.",
            ],
        )

    def test_huan_xi_zan_tan_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        extension = find_extension_by_name(tasks, "歡喜讚歎菩薩行")

        self.assertIsNotNone(extension)
        self.assertEqual(
            extension.get("notes"),
            [
                "Changed the volunteer description to be shorter and more direct, changing \"willingly taking on various duties and caring for Jing Si Hall as if it were their own home\" to \"taking on various duties and treating the Jing Si Hall like their own home.\"",
                "Changed the Master's message to focus more specifically on learning about Tzu Chi volunteers' work around the world instead of the broader idea of \"understanding Tzu Chi's mission.\"",
            ],
        )

    def test_hong_yang_fo_fa_gong_cheng_jiu_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "弘揚佛法共成就":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Added the date because Dharma tour pieces are published quickly and participating Tzu Chi volunteers may be eager to see them soon after the event.",
                "Reworked the introduction to specify that this talk was for the Taipei Buddha Bathing Ceremony team and to credit different volunteer groups in a style closer to the Chinese introduction.",
            ],
        )

    def test_wen_fa_zao_fu_jing_xin_ling_has_editorial_note(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "聞法造福淨心靈":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Added a time marker so the introduction could bring in Tzu Chi volunteers from Central and South America more smoothly and broaden the overall scope.",
            ],
        )

    def test_shi_bing_ru_qin_nuan_xing_lin_has_editorial_note(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "視病如親暖杏林":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Reworked the introduction and summary to more closely reflect the episode's spoken content.",
            ],
        )

    def test_ai_shan_chuan_cheng_di_xiang_he_has_work_time_and_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "愛善傳承締祥和":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(target_task.get("workMinutes"), 50)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Adjusted the conclusion to emphasize the longstanding bond between the Master and Lin's mother, framing the story as an example of members of the Dharma family caring for one another.",
                "Remember to include the closing phrase \"Let's take a listen\" at the end.",
            ],
        )

    def test_shan_yong_ci_sheng_has_editorial_note(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "善用此生厚美德":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Adjusted Tzu Chi branch names to use country or U.S. state names, not city or Taiwan-based forms such as Tzu Chi Tainan or Tzu Chi Taiwan.",
            ],
        )

    def test_reducing_brain_age_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "Reducing Brain Age to Prevent Dementia (人文講堂 - 養腦 防失智 - 曾文毅 [2])":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Reworked the expert introduction to replace a formal academic title with a clearer description for general readers.",
                "Added the name of the featured speaker to the hashtags.",
            ],
        )

    def test_when_liver_disease_goes_unnoticed_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            for stage in task.get("stages", []):
                for extension in stage.get("extensions", []):
                    if extension.get("name") == "All About Health - When Liver Disease Goes Unnoticed (大愛醫生館 - 雲霧肝癌)":
                        target_task = extension
                        break
                if target_task is not None:
                    break
            if target_task is not None:
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Built the post around the episode's patient case and key message instead of relying mainly on outside context.",
                "Mentioned World Hepatitis Day only briefly as the occasion rather than making it central to the content.",
            ],
        )

    def test_tung_tzu_hsien_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            if task.get("name") == "心靈講座(在不確定中走出確定 - 童子賢) 4 個短版":
                target_task = task
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Replaced \"I never socialize\" with wording about avoiding business social events so 不應酬 does not imply avoiding social interaction in general.",
                "Reworked the sentence structure to restore the specific examples of meeting clients, talking to vendors, and checking construction without making the subtitles feel too rushed.",
            ],
        )

    def test_hao_hao_chi_fan_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            if task.get("name") == "大愛全紀實 (好好吃飯) 4 個短版":
                target_task = task
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Simplified the teeth-related phrasing because the Mandarin leaves the detail implicit and difficulty chewing covers the point more naturally.",
                "Changed the grandfather-in-bed line from heartbreaking to feeling helpless so it stays closer to 有一點無力.",
                "Restored the point that Ge Wei-cheng entered long-term care graduate studies before joining his family's facility.",
                "Reworked the restaurant program line to emphasize building a communication channel between restaurants and diners, not only meeting diners' needs.",
            ],
        )

    def test_hong_zhen_yu_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            if task.get("name") == "人文講堂 (獨創思考力 創造影響力 - 洪震宇) 3個短版":
                target_task = task
                break

        self.assertIsNotNone(target_task)
        self.assertEqual(
            target_task.get("notes"),
            [
                "Put unofficial English book titles in parentheses when no official English title exists.",
                "Separated teaching in university EMBA programs from providing corporate training so the two activities remain distinct.",
                "Changed designing rural trips to planning trips to rural areas for more natural English.",
                "Reworked the managers line to show that he asks probing questions and expects business leaders to respond, rather than inviting them to share their challenges.",
                "Replaced the comma splice between the two independent clauses about western and eastern Taiwan with a semicolon.",
                "Restored the detail that they twisted the threads on their thighs like the tribal women did before tying them.",
                "Clarified that part of the store was dedicated to MUJI's own products rather than describing it as MUJI's original space serving the local community.",
                "Replaced the literal phrase worked backward with reflecting from a doctor's perspective to convey how he redefined his purpose.",
            ],
        )

    def test_tzu_chi_story_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            if task.get("name") == "慈濟的故事(臺北的第二個家 、感念臺北因緣 、講藥師經結緣)":
                target_task = task
                break

        self.assertIsNotNone(target_task)
        notes = target_task.get("notes")
        self.assertEqual(len(notes), 28)
        self.assertEqual(notes[0], "Number selected images when more than one image is included.")
        self.assertEqual(
            notes[9],
            "Changed the telephone wording from donating a phone to installing one because the next lines discuss utility poles and phone lines.",
        )
        self.assertEqual(
            notes[10],
            "Numbered selected images and reconsidered the first image because its connection to the title, summary, and content was not clear.",
        )
        self.assertEqual(
            notes[20],
            "Removed the extra space after the question in the Chinese summary.",
        )
        self.assertEqual(
            notes[21],
            "Numbered selected images and avoided using an AI-edited historical photo that changed the color of the Master's robe.",
        )
        self.assertEqual(
            notes[27],
            "Reworked the summaries so the hospital-building context is introduced before mentioning eastern Taiwan medical care.",
        )

    def test_da_ai_xue_han_yi_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            if task.get("name") == "大愛學漢醫（陽虛 血瘀 痰濕體質 防癌方法）":
                target_task = task
                break

        self.assertIsNotNone(target_task)
        notes = target_task.get("notes")
        self.assertEqual(len(notes), 8)
        self.assertEqual(
            notes[0],
            "Removed TCM from the opening doctor title so the super reads more naturally.",
        )
        self.assertEqual(
            notes[7],
            "Changed the herb description to say it works gently rather than suggesting it warms the body.",
        )

    def test_lu_li_has_editorial_notes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        target_task = None
        for task in tasks:
            if task.get("name") == "人文講堂(醫生到我家 - 呂立) 4 個短版":
                target_task = task
                break

        self.assertIsNotNone(target_task)
        notes = target_task.get("notes")
        self.assertEqual(len(notes), 7)
        self.assertEqual(
            notes[0],
            "Simplified the long-term care sentence so it does not overstate health maintenance and keeps the focus on home healthcare.",
        )
        self.assertEqual(
            notes[6],
            "Reworked the case manager explanation so the ending emphasizes seamless continuity of care.",
        )


if __name__ == "__main__":
    unittest.main()
