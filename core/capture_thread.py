"""Camera capture worker and a bounded latest-frame buffer.

The UI can poll the buffer without accumulating stale frames when inference is
slower than the camera. The worker never calls UI methods directly.
"""

import threading
import time
from collections import deque

import cv2
from PyQt5.QtCore import QThread, pyqtSignal

from .reconnect_policy import ReconnectPolicy


class LatestFrameBuffer:
    def __init__(self):
        self._frames = deque(maxlen=1)
        self._lock = threading.Lock()
        self.dropped_count = 0

    def put(self, frame):
        with self._lock:
            if self._frames:
                self._frames.clear()
                self.dropped_count += 1
            self._frames.append(frame)

    def get_latest(self):
        with self._lock:
            if not self._frames:
                return None
            return self._frames.pop()


class CaptureThread(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self, source, fps=15, capture_factory=None, parent=None):
        super().__init__(parent)
        self.source = source
        self.fps = max(1, int(fps))
        self.interval_ms = max(1, round(1000 / self.fps))
        self.capture_factory = capture_factory or cv2.VideoCapture
        self.buffer = LatestFrameBuffer()
        self.policy = ReconnectPolicy()
        self._stop_event = threading.Event()
        self._cap = None
        self._connected = False

    def _set_status(self, connected):
        connected = bool(connected)
        if connected != self._connected:
            self._connected = connected
            self.status_changed.emit(connected)

    def _release_capture(self):
        cap = self._cap
        self._cap = None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def run(self):
        self.policy.reset(time.monotonic())
        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                if self._cap is None:
                    if not self.policy.can_attempt(now):
                        self._stop_event.wait(0.02)
                        continue
                    try:
                        self._cap = self.capture_factory(self.source)
                        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    except Exception:
                        self._cap = None
                    if self._cap is None or not self._cap.isOpened():
                        self._release_capture()
                        self.policy.failed(now)
                        self._set_status(False)
                        continue
                    self.policy.reset(now)
                    self._set_status(True)

                try:
                    ok, frame = self._cap.read()
                except Exception:
                    ok, frame = False, None
                if not ok or frame is None:
                    self._release_capture()
                    self.policy.failed(time.monotonic())
                    self._set_status(False)
                    continue
                self.buffer.put(frame)
                self._stop_event.wait(self.interval_ms / 1000.0)
        finally:
            self._release_capture()
            self._set_status(False)

    def stop(self):
        self._stop_event.set()
        if self.isRunning():
            self.wait(2000)

    def get_latest_frame(self):
        return self.buffer.get_latest()

    @property
    def dropped_frames(self):
        return self.buffer.dropped_count
