import json
import unittest
from pathlib import Path


class TasksJsonTests(unittest.TestCase):
    def test_latest_coworker_task_groups_three_daai_doctor_episodes(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks_coworkers.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))

        last_task = tasks[-1]
        self.assertEqual(
            last_task["name"],
            "3集大愛醫生館（放進去打~輸尿管結石 + 腰椎連環「扁」 + 肺腺癌先禮後兵）",
        )
        self.assertEqual(last_task["contentSeconds"], 418)
        self.assertNotIn("sourceText", last_task)
        self.assertEqual(
            last_task["stages"],
            [
                {
                    "name": "translate",
                    "assignee": "Emily Ding",
                    "startAt": "2026-06-23T05:20:00Z",
                    "deadline": "2026-06-24T03:19:00Z",
                    "workMinutes": 418,
                }
            ],
        )

    def test_last_task_first_extension_work_minutes_is_thirty(self):
        tasks_path = Path(__file__).resolve().parents[1] / "tasks.json"
        tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
        last_task = tasks[-1]
        self.assertEqual(last_task["stages"][0]["extensions"][0]["workMinutes"], 30)

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


if __name__ == "__main__":
    unittest.main()
