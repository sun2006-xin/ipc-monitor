import unittest

import numpy as np

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
        widget._last_analysis_frame_id = None
        widget._last_event_frame_id = None
        widget._last_analysis_errors = []

        snapshot = widget.get_performance_snapshot()

        self.assertEqual(snapshot["analysis_dropped_requests"], 3)

    def test_analysis_result_keeps_frame_id_for_event_correlation(self):
        widget = VideoWidget.__new__(VideoWidget)
        widget._destroying = False
        widget.last_face_detections = []
        widget._last_face_rec_results = []
        widget.last_motion_rects = []
        widget._triggered = []
        widget._trigger_event = lambda *args: widget._triggered.append(args)
        widget.event_triggered = type("Signal", (), {"emit": lambda *_args: None})()
        widget._last_stranger_time = 0
        widget._stranger_cooldown = 8
        widget.motion_alarm = False

        widget._on_analysis_result({
            "frame": np.zeros((2, 2, 3), dtype=np.uint8),
            "frame_id": 42,
            "face_ran": True,
            "face_detections": [{"bbox": [0, 0, 1, 1]}],
            "recognition_results": [],
            "motion_ran": False,
            "errors": [],
        })

        self.assertEqual(widget._last_analysis_frame_id, 42)
        self.assertEqual(widget._triggered[0][2], 42)


if __name__ == "__main__":
    unittest.main()
