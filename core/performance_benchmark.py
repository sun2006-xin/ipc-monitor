"""Repeatable local benchmark for the multi-camera analysis boundary.

This deliberately uses synthetic frames and fake engines. It measures the
analysis pipeline shape and result bookkeeping, not real camera/model speed.
"""

import time
from concurrent.futures import ThreadPoolExecutor

from core.analysis_thread import AnalysisThread
from core.performance_metrics import FrameMetrics


class _SyntheticFaceEngine:
    def detect(self, frame):
        return [{"bbox": [1, 2, 10, 12], "confidence": 0.9, "camera": frame["camera"]}]


class _SyntheticMotionEngine:
    def detect(self, _frame):
        return [(3, 4, 5, 6)]


class _SyntheticRecognizer:
    def recognize_from_frame(self, frame, _bbox):
        return f"camera-{frame['camera']}", False, 0.12, [0.1, 0.2]


def _analyze_camera(camera_id, frames_per_camera):
    face_engine = _SyntheticFaceEngine()
    motion_engine = _SyntheticMotionEngine()
    recognizer = _SyntheticRecognizer()
    results = []
    for frame_id in range(frames_per_camera):
        frame = {"camera": camera_id, "frame_id": frame_id}
        result = AnalysisThread.process_frame(
            frame,
            frame_id,
            face_engine=face_engine,
            motion_engine=motion_engine,
            face_recognizer=recognizer,
            run_face=True,
            run_motion=True,
        )
        results.append(result)
    return results


def run_synthetic_benchmark(camera_count=1, frames_per_camera=30):
    """Run a deterministic synthetic 1/4/9-camera-shaped benchmark.

    The result IDs are grouped by camera so callers can verify that a result
    never gets attributed to another camera. ``queue_dropped`` is intentionally
    zero here because this benchmark processes every submitted request; queue
    pressure is a separate overload experiment.
    """
    camera_count = int(camera_count)
    frames_per_camera = int(frames_per_camera)
    if camera_count < 1 or frames_per_camera < 1:
        raise ValueError("camera_count and frames_per_camera must be positive")

    metrics = FrameMetrics(window=max(2, camera_count * frames_per_camera))
    result_frame_ids = {camera_id: [] for camera_id in range(camera_count)}
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=camera_count) as executor:
        futures = [
            executor.submit(_analyze_camera, camera_id, frames_per_camera)
            for camera_id in range(camera_count)
        ]
        for future in futures:
            for result in future.result():
                metrics.record(result["elapsed_ms"])
                camera_id = result["frame"]["camera"]
                result_frame_ids[camera_id].append(result["frame_id"])
    elapsed_s = time.perf_counter() - started
    snapshot = metrics.snapshot()
    processed = metrics.processed_frames
    return {
        "camera_count": camera_count,
        "frames_per_camera": frames_per_camera,
        "submitted_frames": camera_count * frames_per_camera,
        "processed_frames": processed,
        "queue_dropped": 0,
        "result_frame_ids": result_frame_ids,
        "avg_frame_ms": snapshot["avg_frame_ms"],
        "p95_frame_ms": snapshot["p95_frame_ms"],
        "fps": (processed / elapsed_s) if elapsed_s > 0 else 0.0,
        "synthetic": True,
    }
