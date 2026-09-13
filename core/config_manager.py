import json
import os
import shutil
from datetime import datetime
import uuid
from core.app_paths import R, U


class ConfigManager:
    def __init__(self, config_path=None, backup_path=None):
        # PyInstaller EXE 兼容：配置和备份都是"用户可写"的，绝对不能落到 _MEIPASS 临时目录
        self.config_path = config_path if config_path else U("data/config.json")
        self.backup_path = backup_path if backup_path else U("data/backups/")
        try:
            os.makedirs(self.backup_path, exist_ok=True)
        except Exception:
            pass
        self.config = self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.default_config()
        return self.default_config()

    def save(self):
        if os.path.exists(self.config_path):
            backup_name = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.config_path, os.path.join(self.backup_path, backup_name))
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def default_config(self):
        """Return a privacy-safe configuration with no preset camera."""
        return {
            "devices": [],
            "layout": {"rows": 2, "cols": 2},
            "detection": {
                "face_interval": 5,
                "motion_interval": 5,
                "face_threshold": 0.25,
                "motion_min_area": 1500,
                "face_remove_timeout": 30
            },
            "alarm": {
                "sound_enabled": True,
                "sound_file": R("resources/sounds/alarm.wav"),
                "popup_enabled": False,
                "status_bar_style": "red"
            },
            "language": "zh",
            "recording": {"save_path": U("data/records")},
            "logs": {"max_size_mb": 50, "max_backup": 5}
        }

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def set(self, key, value):
        keys = key.split('.')
        target = self.config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self.save()

    # ===== 设备管理方法 =====
    def get_devices(self):
        return self.config.get("devices", [])

    def get_rtsp_url(self, device):
        """
        构造标准 RTSP URL：rtsp://{username}:{password}@{ip}:{port}/{stream}
        - username / port 兼容老配置没写时退化 admin / 554
        """
        username = device.get('username', 'admin')
        password = device.get('password', '')
        ip = device.get('ip', '')
        port = device.get('port', 554)
        stream = device.get('stream', 'stream1')
        return f"rtsp://{username}:{password}@{ip}:{port}/{stream}"

    @staticmethod
    def redact_rtsp(url: str) -> str:
        """
        🛡 开源打印日志前 脱敏：rtsp://<user>:<secret>@<camera-host>:554/stream
                                       → rtsp://<user>:****@<camera-host>:554/stream
        """
        if not isinstance(url, str) or '://' not in url:
            return url
        try:
            _head, _tail = url.split('://', 1)
            if '@' not in _tail:
                return url
            _userinfo, _rest = _tail.split('@', 1)
            if ':' in _userinfo:
                _u, _p = _userinfo.split(':', 1)
                return f"{_head}://{_u}:****@{_rest}"
            return f"{_head}://****@{_rest}"
        except Exception:
            return url

    def add_device(self, device_data):
        device_data["id"] = str(uuid.uuid4())
        devices = self.config.get("devices", [])
        devices.append(device_data)
        self.config["devices"] = devices
        self.save()

    def remove_device(self, device_id):
        devices = self.config.get("devices", [])
        self.config["devices"] = [d for d in devices if d["id"] != device_id]
        self.save()

    def update_device(self, device_id, new_data):
        devices = self.config.get("devices", [])
        for i, d in enumerate(devices):
            if d["id"] == device_id:
                devices[i].update(new_data)
                break
        self.config["devices"] = devices
        self.save()