"""Repeatable local benchmark for the multi-camera analysis boundary.

This deliberately uses synthetic frames and fake engines. It measures the
analysis pipeline shape and result bookkeeping, not real camera/model speed.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

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


def _read_video(video_path, camera_id, max_frames):
    path = Path(video_path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"cannot open benchmark video: {path}")
    frames = []
    try:
        while len(frames) < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append((camera_id, len(frames), frame))
    finally:
        capture.release()
    if not frames:
        raise ValueError(f"benchmark video has no readable frames: {path}")
    return frames


def run_video_benchmark(video_path, camera_count=1, max_frames=30,
                        face_engine=None, motion_engine_factory=None,
                        face_recognizer=None):
    """Run the real analysis pipeline against a local fixed video.

    The video is opened independently for each logical camera, while callers
    may pass the same loaded face engine to match the application's shared
    detector. No video frames or benchmark output are written to the repo.
    """
    camera_count = int(camera_count)
    max_frames = int(max_frames)
    if camera_count < 1 or max_frames < 1:
        raise ValueError("camera_count and max_frames must be positive")
    path = Path(video_path)
    if not path.is_file():
        raise ValueError(f"benchmark video does not exist: {path}")
    motion_engine_factory = motion_engine_factory or _SyntheticMotionEngine
    started = time.perf_counter()

    def analyze_camera(camera_id):
        motion_engine = motion_engine_factory()
        frames = _read_video(path, camera_id, max_frames)
        results = []
        for _, frame_id, frame in frames:
            results.append((camera_id, AnalysisThread.process_frame(
                frame, frame_id, face_engine=face_engine,
                motion_engine=motion_engine, face_recognizer=face_recognizer,
                run_face=face_engine is not None, run_motion=True,
            )))
        return results

    metrics = FrameMetrics(window=max(2, camera_count * max_frames))
    result_frame_ids = {camera_id: [] for camera_id in range(camera_count)}
    with ThreadPoolExecutor(max_workers=camera_count) as executor:
        futures = [executor.submit(analyze_camera, camera_id)
                   for camera_id in range(camera_count)]
        for future in futures:
            for camera_id, result in future.result():
                metrics.record(result["elapsed_ms"])
                result_frame_ids[camera_id].append(result["frame_id"])
    processed = metrics.processed_frames
    elapsed_s = time.perf_counter() - started
    snapshot = metrics.snapshot()
    return {
        "video": str(path),
        "camera_count": camera_count,
        "max_frames": max_frames,
        "submitted_frames": processed,
        "processed_frames": processed,
        "queue_dropped": 0,
        "result_frame_ids": result_frame_ids,
        "avg_frame_ms": snapshot["avg_frame_ms"],
        "p95_frame_ms": snapshot["p95_frame_ms"],
        "fps": (processed / elapsed_s) if elapsed_s > 0 else 0.0,
        "synthetic": False,
    }
