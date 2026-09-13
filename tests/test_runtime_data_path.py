import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RuntimeDataPathRegressionTest(unittest.TestCase):
    def test_video_widget_uses_user_data_root_helper(self):
        source = (PROJECT_ROOT / "ui" / "video_widget.py").read_text(encoding="utf-8")
        self.assertIn("from core.app_paths import U", source)
        self.assertIn("self.data_root = U(\"data\")", source)
        self.assertNotIn('self.data_root = "data"', source)


if __name__ == "__main__":
    unittest.main()
