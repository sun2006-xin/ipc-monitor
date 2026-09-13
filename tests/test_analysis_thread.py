import unittest

from core.analysis_thread import AnalysisThread


class _FakeFaceEngine:
    def detect(self, frame):
        return [{"bbox": [1, 2, 10, 12], "confidence": 0.9, "marker": frame}]


class _FakeMotionEngine:
    def detect(self, frame):
        return [(3, 4, 5, 6)]


class _FakeRecognizer:
    def recognize_from_frame(self, frame, bbox):
        return "Alice", False, 0.12, [0.1, 0.2]


class AnalysisThreadTests(unittest.TestCase):
    def test_process_frame_returns_requested_analysis(self):
        result = AnalysisThread.process_frame(
            frame="frame-a",
            frame_id=7,
            face_engine=_FakeFaceEngine(),
            motion_engine=_FakeMotionEngine(),
            face_recognizer=_FakeRecognizer(),
            run_face=True,
            run_motion=True,
        )
        self.assertEqual(result["frame_id"], 7)
        self.assertEqual(result["face_detections"][0]["bbox"], [1, 2, 10, 12])
        self.assertEqual(result["motion_rects"], [(3, 4, 5, 6)])
        self.assertEqual(result["recognition_results"][0]["name"], "Alice")
        self.assertGreaterEqual(result["elapsed_ms"], 0.0)

    def test_disabled_analysis_does_not_call_engines(self):
        class ExplodingEngine:
            def detect(self, _frame):
                raise AssertionError("engine should not run")

        result = AnalysisThread.process_frame(
            frame="frame-b",
            frame_id=8,
            face_engine=ExplodingEngine(),
            motion_engine=ExplodingEngine(),
            face_recognizer=None,
            run_face=False,
            run_motion=False,
        )
        self.assertEqual(result["face_detections"], [])
        self.assertEqual(result["motion_rects"], [])


if __name__ == "__main__":
    unittest.main()
