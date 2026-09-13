"""Record privacy-safe memory/thread trends while IPC-Monitor runs."""

import argparse
import sys
import time
from pathlib import Path

try:
    import psutil
except ImportError as exc:  # pragma: no cover - depends on host installation
    raise SystemExit("请先安装 psutil：python -m pip install psutil") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.runtime_soak import append_sample, sample_process


def find_process(pid=None, process_name="IPC-Monitor.exe"):
    if pid is not None:
        return psutil.Process(pid)
    matches = [
        process for process in psutil.process_iter(["name"])
        if (process.info.get("name") or "").lower() == process_name.lower()
    ]
    if not matches:
        raise SystemExit(f"未找到进程 {process_name}，请先启动 EXE 或使用 --pid。")
    if len(matches) > 1:
        raise SystemExit("找到多个目标进程，请使用 --pid 指定唯一进程。")
    return matches[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pid", type=int, help="目标 IPC-Monitor 进程 PID")
    group.add_argument("--process-name", default="IPC-Monitor.exe", help="目标进程名")
    parser.add_argument("--duration-minutes", type=float, default=30.0)
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--output", default="data/logs/runtime_soak.csv")
    args = parser.parse_args(argv)
    if args.duration_minutes <= 0 or args.interval_seconds <= 0:
        parser.error("duration 和 interval 必须大于 0")

    process = find_process(args.pid, args.process_name)
    deadline = time.monotonic() + args.duration_minutes * 60
    count = 0
    while time.monotonic() < deadline:
        try:
            sample = sample_process(process)
            append_sample(args.output, sample)
            count += 1
            print(
                f"[SOAK] sample={count} rss_mb={sample['rss_mb']:.3f} "
                f"threads={sample['threads']} cpu={sample['cpu_percent']:.2f}%"
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print("[SOAK] 目标进程已退出或无法访问，停止采样。")
            break
        time.sleep(min(args.interval_seconds, max(0, deadline - time.monotonic())))
    print(f"SOAK_DONE samples={count} output={Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
