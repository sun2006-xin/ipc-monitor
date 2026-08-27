import unittest

import numpy as np

import core.face_engine as face_engine_module
from core.face_engine import FaceEngine


class _FakeOnnxNet:
    def setInput(self, blob):
        self.blob = blob

    def forward(self, names):
        prediction = np.zeros((1, 1, 6), dtype=np.float32)
        prediction[0, 0] = [320, 320, 200, 200, 0.9, 0.9]
        return [prediction]


class FaceEngineOnnxTests(unittest.TestCase):
    def test_onnx_detection_does_not_require_torch(self):
        engine = FaceEngine.__new__(FaceEngine)
        engine.loaded = True
        engine.model = _FakeOnnxNet()
        engine._use_ultralytics = False
        engine._use_onnx_dnn = True
        engine._use_hub = False
        engine._onnx_output_name = "output0"
        engine.conf_thres = 0.25
        engine.img_size = 640
        engine.stride = 32

        old_torch = face_engine_module.torch
        face_engine_module.torch = None
        try:
            detections = engine.detect(np.zeros((640, 640, 3), dtype=np.uint8))
        finally:
            face_engine_module.torch = old_torch

        self.assertEqual(len(detections), 1)
        self.assertGreater(detections[0]["confidence"], 0.8)


if __name__ == "__main__":
    unittest.main()
