import os
import shutil
import json
from datetime import datetime
from .config_manager import ConfigManager  # ✅ 改为相对导入
from core.app_paths import U


class RecoveryManager:
    def __init__(self, config_path=None, backup_path=None):
        self.config_path = config_path if config_path else U("data/config.json")
        self.backup_path = backup_path if backup_path else U("data/backups/")
        try:
            os.makedirs(self.backup_path, exist_ok=True)
        except Exception:
            pass

    def backup(self):
        if os.path.exists(self.config_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(self.config_path, os.path.join(self.backup_path, f"config_{timestamp}.json"))
            backups = sorted([f for f in os.listdir(self.backup_path) if f.startswith("config_")])
            if len(backups) > 5:
                for f in backups[:-5]:
                    os.remove(os.path.join(self.backup_path, f))

    def restore_latest(self):
        backups = sorted([f for f in os.listdir(self.backup_path) if f.startswith("config_")])
        if backups:
            latest = backups[-1]
            shutil.copy2(os.path.join(self.backup_path, latest), self.config_path)
            return True
        return False

    def auto_repair(self, validator_func):
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            if validator_func(data):
                return True
        except:
            pass
        if self.restore_latest():
            return True
        cfg = ConfigManager()
        cfg.save()
        return True