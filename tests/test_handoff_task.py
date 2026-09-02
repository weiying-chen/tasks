import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import handoff_task


ASSIGNMENT_TEXT = "Alex Chen 請 Elijah Salie edit+定稿3集大愛真健康，謝謝~"


class HandoffTaskTests(unittest.TestCase):
    def make_source_task(self):
        return {
            "id": "64",
            "name": "3集大愛真健康（正確推拉發力 + 每天5分鐘省力起身方式 + 起身變輕鬆、走路更有自信！）",
            "type": "subs",
            "contentSeconds": 650,
            "assigner": "Alex Chen",
            "stages": [
                {
                    "startAt": "2026-08-27T01:40:00Z",
                    "deadline": "2026-08-28T02:20:00Z",
                    "workMinutes": 520,
                    "extensions": [{"name": "unrelated news", "workMinutes": 30}],
                }
            ],
            "sourceText": "original programme request",
        }

    def test_handoff_creates_linked_projection_and_edit_stage(self):
        source = self.make_source_task()
        original = copy.deepcopy(source)

        updated, coworker_id = handoff_task.handoff_task(
            source,
            [],
            ASSIGNMENT_TEXT,
            origin_file="tasks.json",
        )

        self.assertEqual(source, original)
        self.assertEqual(coworker_id, "1")
        self.assertEqual(len(updated), 1)
        projection = updated[0]
        self.assertEqual(projection["origin"], {"file": "tasks.json", "taskId": "64"})
        self.assertEqual(projection["name"], source["name"])
        self.assertEqual(projection["contentSeconds"], 650)
        self.assertEqual(projection["sourceText"], "original programme request")
        self.assertEqual(
            projection["stages"],
            [
                {"name": "translate", "assignee": "Alex Chen", "workMinutes": 520},
                {"name": "edit", "assignee": "Elijah Salie", "workMinutes": 260},
            ],
        )

    def test_handoff_is_idempotent_and_preserves_started_stage(self):
        source = self.make_source_task()
        tasks, coworker_id = handoff_task.handoff_task(
            source,
            [],
            ASSIGNMENT_TEXT,
            origin_file="tasks.json",
        )
        tasks[0]["stages"][1]["startAt"] = "2026-09-02T01:00:00Z"
        tasks[0]["stages"][1]["deadline"] = "2026-09-02T06:20:00Z"

        updated, repeated_id = handoff_task.handoff_task(
            source,
            tasks,
            ASSIGNMENT_TEXT,
            origin_file="tasks.json",
        )

        self.assertEqual(repeated_id, coworker_id)
        self.assertEqual(len(updated), 1)
        edit_stage = updated[0]["stages"][1]
        self.assertEqual(edit_stage["startAt"], "2026-09-02T01:00:00Z")
        self.assertEqual(edit_stage["deadline"], "2026-09-02T06:20:00Z")

    def test_handoff_rejects_assignment_for_different_programme(self):
        with self.assertRaisesRegex(ValueError, "does not match selected task"):
            handoff_task.handoff_task(
                self.make_source_task(),
                [],
                "Alex Chen 請 Elijah Salie edit+定稿3集大愛醫生館，謝謝~",
                origin_file="tasks.json",
            )

    def test_cli_writes_target_and_prints_coworker_id(self):
        script = Path(__file__).resolve().parents[1] / "handoff_task.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "tasks.json"
            target_path = Path(temp_dir) / "tasks_coworkers.json"
            source_path.write_text(json.dumps([self.make_source_task()]), encoding="utf-8")
            target_path.write_text("[]", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--source",
                    str(source_path),
                    "--target",
                    str(target_path),
                    "--task-id",
                    "64",
                    "--print-id",
                    ASSIGNMENT_TEXT,
                ],
                capture_output=True,
                text=True,
            )
            written = json.loads(target_path.read_text(encoding="utf-8"))

        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "1")
        self.assertEqual(written[0]["origin"], {"file": "tasks.json", "taskId": "64"})


if __name__ == "__main__":
    unittest.main()
