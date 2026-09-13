"""Small, dependency-free frame timing metrics for performance baselines."""

from collections import deque
from math import ceil
import time


class FrameMetrics:
    def __init__(self, window=120):
        if int(window) < 2:
            raise ValueError("metrics window must be at least 2")
        self.window = int(window)
        self._samples = deque(maxlen=self.window)
        self.processed_frames = 0
        self.dropped_frames = 0

    def reset(self):
        self._samples.clear()
        self.processed_frames = 0
        self.dropped_frames = 0

    def record(self, duration_ms, now=None):
        timestamp = time.monotonic() if now is None else float(now)
        self._samples.append((timestamp, max(0.0, float(duration_ms))))
        self.processed_frames += 1

    def record_drop(self, now=None):
        # Keep the timestamp argument for future dropped-frame rate reporting.
        _ = time.monotonic() if now is None else float(now)
        self.dropped_frames += 1

    def snapshot(self, now=None):
        samples = list(self._samples)
        durations = [duration for _, duration in samples]
        result = {
            "processed_frames": self.processed_frames,
            "dropped_frames": self.dropped_frames,
            "sample_count": len(samples),
            "avg_frame_ms": (sum(durations) / len(durations)) if durations else 0.0,
            "p95_frame_ms": 0.0,
            "fps": 0.0,
        }
        if durations:
            ordered = sorted(durations)
            result["p95_frame_ms"] = ordered[max(0, ceil(len(ordered) * 0.95) - 1)]
        if len(samples) >= 2:
            span = samples[-1][0] - samples[0][0]
            if span > 0:
                result["fps"] = (len(samples) - 1) / span
        return result
