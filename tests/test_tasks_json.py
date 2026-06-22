import json
import unittest
from pathlib import Path


class TasksJsonTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
