import logging
import os
from logging.handlers import RotatingFileHandler
import json

class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        os.makedirs("data/logs", exist_ok=True)
        self.logger = logging.getLogger("IPC_Monitor")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler = RotatingFileHandler(
            "data/logs/ipc.log", maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        # 控制台输出（可选）
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        self.logger.addHandler(console)

    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def export(self, filepath, format="txt"):
        import shutil
        if format == "txt":
            shutil.copy2("data/logs/ipc.log", filepath)
        elif format == "json":
            with open("data/logs/ipc.log", 'r', encoding='utf-8') as f:
                lines = f.readlines()
            logs = []
            for line in lines:
                if len(line) > 27:
                    logs.append({
                        "time": line[:19],
                        "level": line[20:25],
                        "message": line[27:].strip()
                    })
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)