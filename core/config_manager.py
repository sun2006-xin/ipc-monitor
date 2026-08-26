import json
import os
import shutil
from datetime import datetime
import uuid

class ConfigManager:
    def __init__(self, config_path="data/config.json", backup_path="data/backups/"):
        self.config_path = config_path
        self.backup_path = backup_path
        os.makedirs(backup_path, exist_ok=True)
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
        """
        ⚠ 开源脱敏默认值（避免把作者内网真实 IP / 密码 / 摄像头名带到开源仓库）
        用户首次启动看到示例设备，在 UI「设置」界面直接改成自己的即可。
        """
        return {
            "devices": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "示例-客厅摄像头",            # ← 示例设备名，用户改成自己摄像头的名字即可
                    "username": "admin",                  # ← 新增字段：摄像头登录用户名（之前硬编码admin，现可自定义）
                    "ip": "192.168.1.100",                # ← 示例内网 IP（保留段 192.168.1.100），用户替换为真实 IP
                    "password": "your_password_here",     # ← 占位符，用户请填写摄像头实际登录密码
                    "port": 554,                          # ← 新增字段：RTSP 端口（海康默认 554）
                    "stream": "stream1",
                    "online": False,                      # ← 默认不在线（示例IP不可能真连上，避免误导）
                    "enabled": True
                }
            ],
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
                "sound_file": "resources/sounds/alarm.wav",
                "popup_enabled": False,
                "status_bar_style": "red"
            },
            "language": "zh",
            "recording": {"save_path": "data/records"},
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
        🛡 开源打印日志前 脱敏：rtsp://admin:real_password@192.168.1.100:554/stream1
                                       → rtsp://admin:****@192.168.1.100:554/stream1
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