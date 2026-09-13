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

