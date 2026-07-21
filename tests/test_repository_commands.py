from pathlib import Path
import unittest


class RepositoryCommandsTests(unittest.TestCase):
    def test_makefile_test_target_runs_unittest_discovery(self):
        makefile = Path(__file__).resolve().parents[1] / "Makefile"

        text = makefile.read_text(encoding="utf-8")

        self.assertIn("test:", text)
        self.assertIn("python3 -m unittest discover -s tests", text)


if __name__ == "__main__":
    unittest.main()
