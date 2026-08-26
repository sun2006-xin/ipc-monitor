import sys
import os
import traceback
from datetime import datetime
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# ================================================================
# ✅ 全局异常 / 崩溃保护
# PyQt5 的信号槽（QTimer.timeout / clicked / emit 等）回调中抛出的异常，
# 默认会被 Qt 吞掉或直接 abort 进程 → 用户看到"闪退"。
# 这里安装 sys.excepthook + Qt message handler，把所有异常写入日志文件，
# 并尽量让程序不立即崩溃，方便定位问题。
# ================================================================
_CRASH_LOG_DIR = os.path.join("data", "logs")


def _write_crash_log(title, text):
    try:
        os.makedirs(_CRASH_LOG_DIR, exist_ok=True)
        log_path = os.path.join(_CRASH_LOG_DIR, "crash.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {title} @ {ts} =====\n")
            f.write(text)
            f.write("\n")
    except Exception:
        # 写日志本身也不能让程序崩
        pass


def _global_excepthook(exc_type, exc_value, exc_tb):
    # 1) 终端输出
    traceback.print_exception(exc_type, exc_value, exc_tb)
    # 2) 持久化
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write_crash_log("UNHANDLED EXCEPTION", tb_text)
    # 3) 非致命异常尽量继续（致命错误如 MemoryError 还是会退出）
    try:
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
    except Exception:
        pass


def _qt_message_handler(mode, context, message):
    # Qt 自身的警告 / 致命日志也落地
    label = {
        0: "QtDebug",
        1: "QtWarn",
        2: "QtCritical",
        3: "QtFatal",
        4: "QtInfo",
    }.get(int(mode), f"QtMode{mode}")
    line = f"[{label}] {context.file}:{context.line} ({context.function}) - {message}"
    _write_crash_log("Qt MESSAGE", line)
    # QtFatal 默认会 abort，这里尽力保活一下
    if int(mode) == 3:  # QtFatal
        _write_crash_log("QtFatal ABORT", line)


if __name__ == "__main__":
    # 必须在 QApplication 创建前安装属性
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    try:
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    os.makedirs("data", exist_ok=True)
    os.makedirs(_CRASH_LOG_DIR, exist_ok=True)
    os.makedirs("data/backups", exist_ok=True)

    # 安装全局异常钩子：所有 Python 未捕获异常都会走这里（包括大部分 PyQt 信号槽中的异常）
    sys.excepthook = _global_excepthook

    app = QApplication(sys.argv)

    # 安装 Qt 消息钩子（捕获 Qt 内部警告/错误）
    try:
        from PyQt5.QtCore import qInstallMessageHandler
        qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass

    try:
        from ui.main_window import MainWindow
        win = MainWindow()
        win.show()
    except Exception as e:
        tb = traceback.format_exc()
        _write_crash_log("STARTUP FAILED", tb)
        print("启动失败:", e)
        sys.exit(1)

    sys.exit(app.exec_())