import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.runtime_soak import append_sample, sample_process


class _Memory:
    rss = 12 * 1024 * 1024


class _Process:
    pid = 123

    def memory_info(self):
        return _Memory()

    def num_threads(self):
        return 4

    def cpu_percent(self, _interval):
        return 7.5


class RuntimeSoakTests(unittest.TestCase):
    def test_sample_process_contains_only_health_fields(self):
        sample = sample_process(
            _Process(), datetime(2026, 9, 13, tzinfo=timezone.utc)
        )
        self.assertEqual(sample["pid"], 123)
        self.assertEqual(sample["rss_mb"], 12.0)
        self.assertEqual(sample["threads"], 4)
        self.assertEqual(set(sample), {"timestamp_utc", "pid", "rss_mb", "threads", "cpu_percent"})

    def test_append_sample_writes_header_and_utf8_rows(self):
        sample = sample_process(_Process())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "logs" / "runtime_soak.csv"
            append_sample(path, sample)
            append_sample(path, sample)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("timestamp_utc,pid,rss_mb,threads,cpu_percent", lines[0])


if __name__ == "__main__":
    unittest.main()
