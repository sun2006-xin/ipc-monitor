"""
================================================================
IPC-Monitor · 统一路径中枢（兼容：源码 python main.py / PyInstaller onefile EXE）
================================================================
解决 PyInstaller --onefile --windowed 下最常见的 3 类"找不到文件 / 写进 system32"崩溃：

  1) sys._MEIPASS 临时解压目录：所有「只读资源」（best.pt / *.dat / alarm.wav / *.qm / 3 宣传 PNG）
     打包后都被 PyInstaller 解压到 %TEMP%/_MEIXXXXX/，绝对不能再用 os.getcwd() 或 Path(__file__).parent.parent
     去找这些只读权重，否则 100% FileNotFound → YOLO/dlib/i18n 全链崩。

  2) 用户数据目录（写目录：data/config.json / data/face_db.json / data/logs / snapshots / records ...）
     必须写到 EXE 同级目录，否则：
       - 双击 EXE 的默认 CWD 可能是 C:\Windows\System32（无权限写 → PermissionError 闪退）
       - onefile 每次重新解压 _MEIXXXXX 都是新目录 → 配置/人脸库存了也白存（下次启动全丢）

  3) 双重保障：任何模块只要需要「找某个资源」→ 都先 import app_paths → 调 R() 或 USER_DATA()。
     严禁再写裸 "data/xxx" / "resources/xxx" / "best.pt" / Path(__file__).parent.parent 的相对路径。

================================================================
Apache-2.0
================================================================
"""
import sys
import os
from pathlib import Path


# ----------------------------------------------------------------
# ① BUNDLE_ROOT：只读资源的根目录（源码 → 项目根；EXE → sys._MEIPASS）
# ----------------------------------------------------------------
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # 打包 onefile EXE 运行中：所有 best.pt / models/*.dat / resources/*.qm / docs/*.png
    # 都被 PyInstaller 解压到这里（绝对路径，只读读一次就行，别往里面写）
    BUNDLE_ROOT = Path(sys._MEIPASS).resolve()
    _RUN_MODE = "EXE_ONEFILE"
else:
    # 源码模式：main.py 所在目录 = 项目根（= BUNDLE_ROOT）
    BUNDLE_ROOT = Path(__file__).resolve().parent.parent
    _RUN_MODE = "SRC_PYTHON"


# ----------------------------------------------------------------
# ② USER_DATA_ROOT：可写用户数据根目录（源码 → 项目根；EXE → EXE 所在目录）
# ----------------------------------------------------------------
if _RUN_MODE == "EXE_ONEFILE":
    # sys.executable = dist/IPC-Monitor.exe 的绝对路径
    # 权重/配置/人脸库/日志 → 全部跟 EXE 放一起，用户复制整文件夹就能用
    USER_DATA_ROOT = Path(sys.executable).resolve().parent
else:
    # 源码模式：main.py 同级
    USER_DATA_ROOT = BUNDLE_ROOT


# ----------------------------------------------------------------
# ③ 对外 API：R("relative/path") 查 只读资源；U("relative/path") 查 可写路径
# ----------------------------------------------------------------
def R(rel_path: str) -> str:
    """只读资源：打包后在 _MEIPASS 里，源码在项目根。不存在也返回路径，由调用方自己判断 exists。"""
    return str(BUNDLE_ROOT / rel_path.replace("/", os.sep))


def U(rel_path: str) -> str:
    """可写数据：打包后写到 EXE 同目录；源码写到项目根。如果父目录不存在，makedirs。"""
    full = USER_DATA_ROOT / rel_path.replace("/", os.sep)
    try:
        os.makedirs(str(full.parent), exist_ok=True)
    except Exception:
        pass
    return str(full)


def RUN_MODE() -> str:
    return _RUN_MODE


# ----------------------------------------------------------------
# ④ 启动早期一次性把所有需要写的子目录建立好（防止写日志时找不到父目录闪退）
# ----------------------------------------------------------------
def ensure_user_dirs():
    for d in (
        "data",
        "data/logs",
        "data/backups",
        "data/snapshots",
        "data/records",
        "data/motions",
        "data/faces",
    ):
        try:
            os.makedirs(U(d), exist_ok=True)
        except Exception:
            pass
    return USER_DATA_ROOT


# ----------------------------------------------------------------
# ⑤ 启动调试打印（import 即执行一次），方便崩溃时看路径到底指到哪
# ----------------------------------------------------------------
print(f"[AppPaths] mode={_RUN_MODE}")
print(f"[AppPaths] BUNDLE_ROOT(read-only) = {BUNDLE_ROOT}")
print(f"[AppPaths] USER_DATA_ROOT(writable) = {USER_DATA_ROOT}")
try:
    # 检查核心只读权重是否在 BUNDLE_ROOT 里，立即打 WARN，免得 YOLO 失败栈太深看不出
    for w in ("best.pt", "best.onnx"):
        p = BUNDLE_ROOT / w
        print(f"[AppPaths] R({w}) exists? {p.exists()}  -> {p}")
    for w in ("models/shape_predictor_68_face_landmarks.dat", "models/dlib_face_recognition_resnet_model_v1.dat"):
        p = BUNDLE_ROOT / w
        print(f"[AppPaths] R({w}) exists? {p.exists()}  -> {p}")
except Exception:
    pass
