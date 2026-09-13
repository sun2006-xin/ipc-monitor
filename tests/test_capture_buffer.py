import unittest

from core.capture_thread import LatestFrameBuffer


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


if __name__ == "__main__":
    unittest.main()
