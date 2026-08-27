import logging
import os
from logging.handlers import RotatingFileHandler
import json
from core.app_paths import U


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_logger()
        return cls._instance

    def _init_logger(self):
        # PyInstaller EXE：日志必须写到 EXE 同级 data/logs（否则大概率写进 system32 直接闪退）
        self._log_dir = U("data/logs")
        self._log_file = U("data/logs/ipc.log")
        self.logger = logging.getLogger("IPC_Monitor")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        try:
            file_handler = RotatingFileHandler(
                self._log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as _le:
            # 写日志失败也不能让进程崩（EXE 从只读目录双击时可能触发）
            print(f"[Logger] WARN RotatingFileHandler 失败，跳过写盘: {_le}")
        # 控制台输出（PyInstaller --windowed 下 stdout=None，StreamHandler 内部会安全处理）
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
            shutil.copy2(self._log_file, filepath)
        elif format == "json":
            with open(self._log_file, 'r', encoding='utf-8') as f:
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
