import os
import json
import re
import tempfile
import unittest

from core.app_paths import R
from core.config_manager import ConfigManager


class ResourcePathTests(unittest.TestCase):
    def test_bundled_resources_resolve_to_existing_absolute_paths(self):
        for relative in (
            "best.onnx",
            "models/shape_predictor_68_face_landmarks.dat",
            "models/dlib_face_recognition_resnet_model_v1.dat",
            "resources/sounds/alarm.wav",
        ):
            path = R(relative)
            self.assertTrue(os.path.isabs(path), path)
            self.assertTrue(os.path.exists(path), path)

    def test_default_config_uses_absolute_runtime_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ConfigManager(
                config_path=os.path.join(directory, "config.json"),
                backup_path=os.path.join(directory, "backups"),
            )
            self.assertTrue(os.path.isabs(manager.get("alarm.sound_file")))
            self.assertTrue(os.path.isabs(manager.get("recording.save_path")))

    def test_default_config_contains_no_camera_credentials_or_private_ip(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ConfigManager(
                config_path=os.path.join(directory, "config.json"),
                backup_path=os.path.join(directory, "backups"),
            )
            config = manager.default_config()
            serialized = json.dumps(config, ensure_ascii=False)

            self.assertEqual(config["devices"], [])
            self.assertNotRegex(serialized, r"(?i)password|passwd|rtsp://")
            self.assertNotRegex(
                serialized,
                r"(?<!\d)(?:10\.(?:\d{1,3}\.){2}\d{1,3}|"
                r"192\.168\.(?:\d{1,3}\.)\d{1,3}|"
                r"172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})(?!\d)",
            )


if __name__ == "__main__":
    unittest.main()
