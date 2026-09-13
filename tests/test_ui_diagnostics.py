import unittest

from ui.main_window import MainWindow


class UiDiagnosticsTests(unittest.TestCase):
    def test_format_diagnostics_aggregates_frame_and_drop_fields(self):
        text = MainWindow._format_diagnostics([
            {"analysis_dropped_requests": 2, "last_analysis_frame_id": 17, "last_event_frame_id": 15},
            {"analysis_dropped_requests": 1, "last_analysis_frame_id": 21, "last_event_frame_id": None},
        ])

        self.assertIn("在线 2", text)
        self.assertIn("分析丢弃 3", text)
        self.assertIn("最近分析帧 21", text)
        self.assertIn("最近告警帧 15", text)

    def test_format_diagnostics_has_placeholders_when_empty(self):
        self.assertEqual(
            MainWindow._format_diagnostics([]),
            "诊断 | 在线 0 | 分析丢弃 0 | 最近分析帧 -- | 最近告警帧 --",
        )


if __name__ == "__main__":
    unittest.main()
