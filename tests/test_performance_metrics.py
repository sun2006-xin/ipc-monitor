import unittest

from core.performance_metrics import FrameMetrics
from ui.video_widget import VideoWidget


class FrameMetricsTests(unittest.TestCase):
    def test_snapshot_reports_windowed_latency_and_fps(self):
        metrics = FrameMetrics(window=4)
        metrics.record(10.0, now=100.0)
        metrics.record(20.0, now=101.0)
        metrics.record(30.0, now=102.0)
        snapshot = metrics.snapshot(now=102.0)
        self.assertEqual(snapshot["processed_frames"], 3)
        self.assertEqual(snapshot["dropped_frames"], 0)
        self.assertAlmostEqual(snapshot["avg_frame_ms"], 20.0)
        self.assertAlmostEqual(snapshot["fps"], 1.0)

    def test_window_is_bounded_and_drops_are_counted(self):
        metrics = FrameMetrics(window=2)
        metrics.record(5.0, now=10.0)
        metrics.record_drop(now=10.1)
        metrics.record(15.0, now=11.0)
        metrics.record(25.0, now=12.0)
        snapshot = metrics.snapshot(now=12.0)
        self.assertEqual(snapshot["processed_frames"], 3)
        self.assertEqual(snapshot["dropped_frames"], 1)
        self.assertEqual(snapshot["sample_count"], 2)
        self.assertAlmostEqual(snapshot["p95_frame_ms"], 25.0)

    def test_video_snapshot_includes_analysis_queue_drops(self):
        widget = VideoWidget.__new__(VideoWidget)
        widget.performance_metrics = FrameMetrics()
        widget.analysis_thread = type("Thread", (), {"dropped_requests": 3})()

        snapshot = widget.get_performance_snapshot()

        self.assertEqual(snapshot["analysis_dropped_requests"], 3)


if __name__ == "__main__":
    unittest.main()
