import unittest
import time

from core.capture_thread import CaptureThread, LatestFrameBuffer


class LatestFrameBufferTests(unittest.TestCase):
    def test_buffer_keeps_only_latest_frame(self):
        buffer = LatestFrameBuffer()
        buffer.put("frame-1")
        buffer.put("frame-2")
        self.assertEqual(buffer.get_latest(), "frame-2")
        self.assertIsNone(buffer.get_latest())

    def test_drop_count_reports_overwritten_frames(self):
        buffer = LatestFrameBuffer()
        buffer.put("frame-1")
        buffer.put("frame-2")
        buffer.put("frame-3")
        self.assertEqual(buffer.dropped_count, 2)
        self.assertEqual(buffer.get_latest(), "frame-3")


class CaptureThreadLifecycleTests(unittest.TestCase):
    def test_stop_releases_capture_and_ends_worker(self):
        class FakeCapture:
            def __init__(self):
                self.released = False

            def set(self, *_args):
                return True

            def isOpened(self):
                return not self.released

            def read(self):
                return (True, "frame")

            def release(self):
                self.released = True

        fake = FakeCapture()
        worker = CaptureThread("fake", fps=1000, capture_factory=lambda _source: fake)
        worker.start()
        deadline = time.monotonic() + 1.0
        while worker.get_latest_frame() is None and time.monotonic() < deadline:
            time.sleep(0.005)
        worker.stop()
        self.assertFalse(worker.isRunning())
        self.assertTrue(fake.released)


if __name__ == "__main__":
    unittest.main()
