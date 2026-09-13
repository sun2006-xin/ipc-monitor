"""Background face/motion analysis with a latest-request queue."""

import threading
import time

from PyQt5.QtCore import QThread, pyqtSignal


class AnalysisThread(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, face_engine=None, motion_engine=None, parent=None):
        super().__init__(parent)
        self.face_engine = face_engine
        self.motion_engine = motion_engine
        self._condition = threading.Condition()
        self._latest_request = None
        self._stop_requested = False
        self.dropped_requests = 0

    @staticmethod
    def process_frame(frame, frame_id, face_engine=None, motion_engine=None,
                      run_face=True, run_motion=True):
        started = time.perf_counter()
        result = {
            "frame": frame,
            "frame_id": frame_id,
            "face_detections": [],
            "motion_rects": [],
            "face_ran": bool(run_face and face_engine is not None),
            "motion_ran": bool(run_motion and motion_engine is not None),
            "errors": [],
        }
        if run_face and face_engine is not None:
            try:
                result["face_detections"] = face_engine.detect(frame) or []
            except Exception as exc:
                result["errors"].append(f"face: {exc}")
        if run_motion and motion_engine is not None:
            try:
                result["motion_rects"] = motion_engine.detect(frame) or []
            except Exception as exc:
                result["errors"].append(f"motion: {exc}")
        result["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
        return result

    def submit(self, frame, frame_id, run_face=True, run_motion=True):
        try:
            safe_frame = frame.copy()
        except AttributeError:
            safe_frame = frame
        request = (safe_frame, frame_id, bool(run_face), bool(run_motion))
        with self._condition:
            if self._stop_requested:
                return False
            if self._latest_request is not None:
                self.dropped_requests += 1
            self._latest_request = request
            self._condition.notify()
        return True

    def run(self):
        while True:
            with self._condition:
                while self._latest_request is None and not self._stop_requested:
                    self._condition.wait()
                if self._stop_requested and self._latest_request is None:
                    return
                request = self._latest_request
                self._latest_request = None
            frame, frame_id, run_face, run_motion = request
            result = self.process_frame(
                frame, frame_id, self.face_engine, self.motion_engine,
                run_face, run_motion,
            )
            self.result_ready.emit(result)

    def stop(self):
        with self._condition:
            self._stop_requested = True
            self._latest_request = None
            self._condition.notify_all()
        if self.isRunning():
            self.wait(2000)
