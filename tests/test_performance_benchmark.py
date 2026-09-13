import unittest

from core.performance_benchmark import (
    run_queue_pressure_benchmark,
    run_synthetic_benchmark,
    run_video_benchmark,
)


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_benchmark_covers_each_camera_and_preserves_result_frame_ids(self):
        report = run_synthetic_benchmark(camera_count=4, frames_per_camera=6)

        self.assertEqual(report["camera_count"], 4)
        self.assertEqual(report["submitted_frames"], 24)
        self.assertEqual(report["processed_frames"], 24)
        self.assertEqual(report["queue_dropped"], 0)
        self.assertEqual(report["result_frame_ids"], {
            camera: list(range(6)) for camera in range(4)
        })
        self.assertGreaterEqual(report["p95_frame_ms"], 0.0)
        self.assertGreaterEqual(report["fps"], 0.0)

    def test_benchmark_rejects_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            run_synthetic_benchmark(camera_count=0, frames_per_camera=4)
        with self.assertRaises(ValueError):
            run_synthetic_benchmark(camera_count=1, frames_per_camera=0)

    def test_video_benchmark_rejects_missing_local_input(self):
        with self.assertRaises(ValueError):
            run_video_benchmark("does-not-exist.mp4", camera_count=1, max_frames=4)

    def test_queue_pressure_keeps_only_latest_pending_frame(self):
        report = run_queue_pressure_benchmark(frame_count=12, delay_ms=5)

        self.assertEqual(report["submitted_frames"], 12)
        self.assertGreaterEqual(report["queue_dropped"], 11)
        self.assertEqual(report["processed_frames"], 1)
        self.assertEqual(report["result_frame_ids"], [11])


if __name__ == "__main__":
    unittest.main()
