import tempfile
import unittest
from pathlib import Path

from core.runtime_soak import append_sample, assess_soak_summary, summarize_soak_csv


class RuntimeSoakSummaryTests(unittest.TestCase):
    def test_summary_reports_memory_and_thread_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.csv"
            for rss, threads in ((10.0, 3), (12.5, 4), (11.0, 4)):
                append_sample(path, {
                    "timestamp_utc": "2026-09-13T00:00:00+00:00",
                    "pid": 123,
                    "rss_mb": rss,
                    "threads": threads,
                    "cpu_percent": 5.0,
                })
            summary = summarize_soak_csv(path)
        self.assertEqual(summary["samples"], 3)
        self.assertEqual(summary["start_rss_mb"], 10.0)
        self.assertEqual(summary["end_rss_mb"], 11.0)
        self.assertEqual(summary["max_rss_mb"], 12.5)
        self.assertEqual(summary["rss_delta_mb"], 1.0)
        self.assertEqual(summary["thread_delta"], 1)

    def test_summary_rejects_empty_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.csv"
            path.write_text("timestamp_utc,pid,rss_mb,threads,cpu_percent\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                summarize_soak_csv(path)

    def test_assessment_marks_growth_for_review_without_claiming_leak(self):
        result = assess_soak_summary({"rss_delta_mb": 60, "thread_delta": 3})
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(len(result["warnings"]), 2)

    def test_assessment_passes_stable_summary(self):
        self.assertEqual(
            assess_soak_summary({"rss_delta_mb": 1, "thread_delta": 0}),
            {"status": "PASS", "warnings": []},
        )


if __name__ == "__main__":
    unittest.main()
