"""Privacy-safe process health sampling for long-running camera acceptance tests."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path


FIELDNAMES = ("timestamp_utc", "pid", "rss_mb", "threads", "cpu_percent")


def sample_process(process, timestamp=None):
    """Return one serializable process-health sample from a psutil-like object."""
    memory = process.memory_info()
    return {
        "timestamp_utc": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "pid": int(process.pid),
        "rss_mb": round(float(memory.rss) / (1024 * 1024), 3),
        "threads": int(process.num_threads()),
        "cpu_percent": round(float(process.cpu_percent(None)), 2),
    }


def append_sample(path, sample):
    """Append a sample and create a UTF-8 CSV header on first write."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    new_file = not target.exists() or target.stat().st_size == 0
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        writer.writerow({key: sample[key] for key in FIELDNAMES})


def summarize_soak_csv(path):
    """Summarize a soak CSV without retaining individual samples in memory."""
    rows = []
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    if not rows:
        raise ValueError("CSV 没有采样记录")
    rss = [float(row["rss_mb"]) for row in rows]
    threads = [int(row["threads"]) for row in rows]
    cpu = [float(row["cpu_percent"]) for row in rows]
    return {
        "samples": len(rows),
        "start_timestamp_utc": rows[0]["timestamp_utc"],
        "end_timestamp_utc": rows[-1]["timestamp_utc"],
        "start_rss_mb": rss[0],
        "end_rss_mb": rss[-1],
        "max_rss_mb": max(rss),
        "rss_delta_mb": round(rss[-1] - rss[0], 3),
        "max_threads": max(threads),
        "thread_delta": threads[-1] - threads[0],
        "avg_cpu_percent": round(sum(cpu) / len(cpu), 2),
    }

