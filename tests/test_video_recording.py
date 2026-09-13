import unittest
from unittest.mock import patch

import numpy as np

from ui.video_widget import VideoWidget


class _FakeWriter:
    def __init__(self, opened=True, events=None, label="writer"):
        self.opened = opened
        self.release_count = 0
        self.events = events
        self.label = label

    def isOpened(self):
        return self.opened

    def release(self):
        self.release_count += 1
        if self.events is not None:
            self.events.append(f"release:{self.label}")


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

    def test_hour_rotation_releases_old_writer_before_creating_new(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        widget = self._widget(frame)
        widget._schedule_record_enabled = True
        widget._record_hour_key = ""
        widget.cap = None
        events = []
        writers = iter([
            _FakeWriter(events=events, label="old"),
            _FakeWriter(events=events, label="new"),
        ])

        def make_writer(*_args):
            events.append("create")
            return next(writers)

        with patch("ui.video_widget.cv2.VideoWriter", side_effect=make_writer):
            widget._ensure_scheduled_recording(
                frame, now=__import__("datetime").datetime(2026, 9, 13, 10, 59)
            )
            widget._ensure_scheduled_recording(
                frame, now=__import__("datetime").datetime(2026, 9, 13, 11, 0)
            )

        self.assertEqual(events, ["create", "release:old", "create"])
        self.assertTrue(widget.is_recording)
        self.assertEqual(widget._record_hour_key, "20260913_11")


if __name__ == "__main__":
    unittest.main()
