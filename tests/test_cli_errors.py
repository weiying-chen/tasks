import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path


class CliErrorTests(unittest.TestCase):
    def test_invalid_input_is_one_line_without_traceback(self):
        script = Path(__file__).resolve().parent.parent / "text_to_json.py"
        proc = subprocess.run(
            [sys.executable, str(script), "random garbage input"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Cannot parse input as posts/news/subs", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_view_latest_task_accepts_file_arg(self):
        script = Path(__file__).resolve().parent.parent / "view_latest_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks_coworkers.json"
            tasks_path.write_text('[{"id":"1","name":"Coworker","stages":[{"type":"subs","startAt":"2026-06-02T01:00:00Z","workMinutes":240}]}]', encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--file", str(tasks_path), "--once"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Name: Coworker", proc.stdout)

    def test_view_task_wrapper_accepts_file_arg(self):
        script = Path(__file__).resolve().parent.parent / "view_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks_coworkers.json"
            tasks_path.write_text('[{"id":"1","name":"Coworker","stages":[{"type":"subs","startAt":"2026-06-02T01:00:00Z","workMinutes":240}]}]', encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--file", str(tasks_path), "--once"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Name: Coworker", proc.stdout)

    def test_notes_target_error_is_one_line_without_traceback(self):
        script = Path(__file__).resolve().parent.parent / "text_to_json.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--parent-id", "6", "--target", "notes", "not a bullet line"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Cannot add notes.", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_news_add_without_parent_errors_instead_of_creating_task(self):
        script = Path(__file__).resolve().parent.parent / "text_to_json.py"
        text = (
            "大家好，新聞分配如下，麻煩7/1 (三) 早上開始做，謝謝大家~\n\n"
            "7/1\n\n"
            "張牧軒 Shawn: 溫哥華人校結業 1:14\n"
            "Alex Chen: 菲獨立日義診 3:29\n"
            "Elijah Salie: 尼單親媽修繕 4:26"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks.json"
            tasks_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "45",
                            "name": "大愛學漢醫（陽虛 血瘀 痰濕體質 防癌方法）",
                            "type": "subs",
                            "stages": [
                                {
                                    "startAt": "2026-06-30T07:09:00Z",
                                    "deadline": "2026-07-01T08:45:00Z",
                                    "workMinutes": 576,
                                }
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(script), "--infile", str(tasks_path), text],
                capture_output=True,
                text=True,
            )
            updated = json.loads(tasks_path.read_text(encoding="utf-8"))

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Cannot parse input as posts/news/subs", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(len(updated), 1)
        self.assertNotIn("extensions", updated[0]["stages"][0])

    def test_assign_task_cli_uses_latest_coworker_task(self):
        script = Path(__file__).resolve().parent.parent / "assign_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks_coworkers.json"
            tasks_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "1",
                            "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                            "type": "subs",
                            "contentSeconds": 364,
                        },
                        {
                            "id": "2",
                            "name": "3集大愛醫生館（放進去打~輸尿管結石 + 腰椎連環「扁」 + 肺腺癌先禮後兵）",
                            "type": "subs",
                            "contentSeconds": 418,
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--infile",
                    str(tasks_path),
                    "Alex Chen 請 Emily Ding 翻譯3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），謝謝~",
                ],
                capture_output=True,
                text=True,
            )
            updated = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("stages", updated[0])
        self.assertEqual(updated[1]["stages"][0]["assignee"], "Emily Ding")
        self.assertEqual(updated[1]["stages"][0]["workMinutes"], 418)

    def test_confirm_task_start_cli_uses_latest_coworker_task(self):
        script = Path(__file__).resolve().parent.parent / "assign_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_path = Path(temp_dir) / "tasks_coworkers.json"
            tasks_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "1",
                            "name": "3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈）",
                            "assigner": "Alex Chen",
                            "stages": [
                                {
                                    "type": "subs",
                                    "name": "translate",
                                    "assignee": "Emily Ding",
                                    "workMinutes": 364,
                                }
                            ],
                        },
                        {
                            "id": "2",
                            "name": "3集大愛醫生館（放進去打~輸尿管結石 + 腰椎連環「扁」 + 肺腺癌先禮後兵）",
                            "assigner": "Alex Chen",
                            "stages": [
                                {
                                    "type": "subs",
                                    "name": "translate",
                                    "assignee": "Emily Ding",
                                    "workMinutes": 418,
                                }
                            ],
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--mode",
                    "task-start",
                    "--infile",
                    str(tasks_path),
                    "接下來我會開始翻譯3集大愛醫生館（不是潰瘍的十二指腸出血 + 壯年出血在腦內 + 腎癌迷走下腔靜脈），deadline從6/23 (三)13:00起算，再麻煩Alex Chen 方便時幫我設 deadline與傳稿子，謝謝。",
                ],
                capture_output=True,
                text=True,
            )
            updated = json.loads(tasks_path.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("startAt", updated[0]["stages"][0])
        self.assertEqual(updated[1]["stages"][0]["startAt"], "2026-06-23T05:00:00Z")
        self.assertEqual(updated[1]["stages"][0]["deadline"], "2026-06-24T02:58:00Z")


if __name__ == "__main__":
    unittest.main()
