import sys
import os
import io
import traceback
from datetime import datetime

# ================================================================
# 最最顶端 stdout/stderr 编码双保险（必须放在 PyQt5 / core / ui 所有 import 之前！）
# 旧问题 1：PowerShell 用 -RedirectStandardOutput 给 --windowed GUI 进程强制分配 GBK(cp936) 管道
#          → 模块级 print 只要有中文/emoji 非 GBK 字符 → UnicodeEncodeError → 进程 ExitCode=1 死在 import 阶段
#          （crash handler / Logger 都还没装，连日志都没有）
# 旧问题 2：老师那边如果启动命令被重定向，同样会触发 1；
#          另外还有 stdout==None 的情况（PyInstaller --windowed 双击），不绑定会变成 NUL 写错误
# 处理原则：全都改成 UTF-8 + errors='replace'，任何 print 编码错误绝不影响程序启动
# ================================================================
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
for _stream_name in ('stdout', 'stderr'):
    try:
        _orig = getattr(sys, _stream_name, None)
        if _orig is None:
            # PyInstaller --windowed 双击：stdout/stderr 默认 None → 绑到 devnull UTF-8 写
            _null = open(os.devnull, 'w', encoding='utf-8', errors='replace')
            setattr(sys, _stream_name, _null)
            continue
        _buf = getattr(_orig, 'buffer', None)
        if _buf is not None:
            try:
                _wrapped = io.TextIOWrapper(
                    _buf, encoding='utf-8', errors='replace', line_buffering=True
                )
                setattr(sys, _stream_name, _wrapped)
                continue
            except Exception:
                pass
        # 兜底：有些进程重定向没有 buffer，直接 reconfigure
        try:
            _cfg = getattr(_orig, 'reconfigure', None)
            if callable(_cfg):
                _cfg(encoding='utf-8', errors='replace')
        except Exception:
            pass
    except Exception:
        pass


# ================================================================
# 【根治 c10.dll 1114 偶发 DLL 初始化失败】—— PyTorch 在 PyQt5/OpenCV 后初始化偶发 1114
#   根因（经验 783954/811072 交叉验证）：PyQt5.Qt5Core / Qt5Gui / cv2 / numpy.core._multiarray_umath
#   会在进程地址空间先占 64KB 对齐页，加载顺序竞争后导致 c10.dll 的 LdrpProcessWork 初始化回调里
#   GetModuleHandleExW / TlsAlloc 竞争失败 → [WinError 1114] DLL 初始化例程失败。
#   唯一稳定修复：所有第三方库都 import 前，先把 torch/torchvision/torchaudio/ultralytics 全 import 掉。
#   失败最多重试 2 次（间隔 1s），3 次都失败才放过（face_engine 仍有 4 级降级兜底 + WARN 提示）。
# ================================================================
_TORCH_PRELOAD_OK = False
try:
    import time as _t_pc_t
    for _attempt in (1, 2, 3):
        try:
            import torch
            import torchvision
            import torchaudio
            import ultralytics
            _TORCH_PRELOAD_OK = True
            print(f"[MAIN] torch 预热成功（attempt={_attempt}）："
                  f"torch={torch.__version__} / torchvision={torchvision.__version__} / "
                  f"torchaudio={torchaudio.__version__} / ultralytics={ultralytics.__version__}")
            break
        except Exception as _attempt_err:
            print(f"[MAIN] torch 预热 attempt={_attempt} 失败：{_attempt_err}")
            if _attempt < 3:
                try:
                    # 清残留临时 torch 缓存
                    for _k in list(sys.modules.keys()):
                        if _k == 'torch' or _k.startswith('torch.') or _k == 'ultralytics' or _k.startswith('ultralytics.'):
                            try: del sys.modules[_k]
                            except Exception: pass
                except Exception: pass
                _t_pc_t.sleep(1.0)
except Exception as _preload_total_err:
    print(f"[MAIN] torch 预热段异常，继续启动（face_engine 自带 4 级降级兜底）：{_preload_total_err}")


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