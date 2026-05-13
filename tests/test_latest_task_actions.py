import unittest

import view_latest_task as ltv


class LatestTaskActionsTests(unittest.TestCase):
    def test_find_latest_task_id(self):
        tasks = [
            {"id": "1", "name": "A", "children": []},
            {"id": "7", "name": "B", "children": []},
        ]
        self.assertEqual(ltv.find_latest_task_id(tasks), "7")

    def test_build_add_to_latest_command(self):
        cmd = ltv.build_add_to_latest_command("/tmp", "9")
        self.assertEqual(
            cmd,
            ["python3", "/tmp/text_to_json.py", "--parent-id", "9", "__CLIPBOARD__"],
        )


if __name__ == "__main__":
    unittest.main()
