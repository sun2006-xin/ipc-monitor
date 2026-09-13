import unittest
from unittest.mock import patch

import numpy as np

from ui.video_widget import VideoWidget


class _FakeWriter:
    def __init__(self, opened=True):
        self.opened = opened
        self.release_count = 0

    def isOpened(self):
        return self.opened

    def release(self):
        self.release_count += 1


class VideoRecordingLifecycleTests(unittest.TestCase):
    def _widget(self, frame=None):
        widget = VideoWidget.__new__(VideoWidget)
        widget._destroying = False
        widget.is_recording = False
        widget.video_writer = None
        widget.current_frame = frame
        widget.data_root = "D:/ipc-test-data"
        widget.name_label = type("Label", (), {"text": lambda self: "cam-1"})()
        widget._frame_size = (0, 0)
        return widget

    def test_start_record_requires_a_real_frame(self):
        widget = self._widget()

        with patch("ui.video_widget.cv2.VideoWriter") as factory:
            self.assertFalse(widget.start_record())

        factory.assert_not_called()
        self.assertFalse(widget.is_recording)
        self.assertIsNone(widget.video_writer)

    def test_start_record_uses_frame_size_and_stop_releases_once(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        widget = self._widget(frame)
        writer = _FakeWriter()

        with patch("ui.video_widget.cv2.VideoWriter", return_value=writer) as factory:
            self.assertTrue(widget.start_record())

        self.assertEqual(factory.call_args.args[3], (640, 480))
        self.assertEqual(widget._frame_size, (640, 480))
        self.assertTrue(widget.is_recording)
        widget.stop_record()
        widget.stop_record()

        self.assertFalse(widget.is_recording)
        self.assertIsNone(widget.video_writer)
        self.assertEqual(writer.release_count, 1)


if __name__ == "__main__":
    unittest.main()
