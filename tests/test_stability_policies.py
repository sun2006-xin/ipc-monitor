import json
import tempfile
import unittest
from pathlib import Path

from core.config_manager import ConfigManager
from core.recovery import RecoveryManager
from core.reconnect_policy import ReconnectPolicy


class ReconnectPolicyTests(unittest.TestCase):
    def test_backoff_is_time_based_and_capped(self):
        policy = ReconnectPolicy(initial_delay=1.0, max_delay=4.0)
        policy.reset(now=100.0)
        self.assertTrue(policy.can_attempt(now=100.0))
        policy.failed(now=100.0)
        self.assertFalse(policy.can_attempt(now=100.9))
        self.assertTrue(policy.can_attempt(now=101.0))
        policy.failed(now=101.0)
        self.assertEqual(policy.next_attempt_at, 103.0)
        for now in (103.0, 107.0, 111.0):
            policy.failed(now=now)
        self.assertEqual(policy.delay, 4.0)


class ConfigRecoveryTests(unittest.TestCase):
    def test_corrupt_config_is_repaired_in_requested_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "data" / "config.json"
            backup_path = root / "data" / "backups"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("{broken", encoding="utf-8")

            manager = ConfigManager(config_path=config_path, backup_path=backup_path)
            self.assertEqual(manager.get_devices(), [])
            recovery = RecoveryManager(config_path=config_path, backup_path=backup_path)
            self.assertTrue(recovery.auto_repair(lambda data: isinstance(data, dict)))

            repaired = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(repaired["devices"], [])
            self.assertTrue((config_path.parent / "config.json").exists())

    def test_save_is_atomic_and_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "nested" / "config.json"
            backup_path = Path(tmp) / "nested" / "backups"
            manager = ConfigManager(config_path=config_path, backup_path=backup_path)
            manager.set("language", "en")
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["language"], "en")


if __name__ == "__main__":
    unittest.main()
