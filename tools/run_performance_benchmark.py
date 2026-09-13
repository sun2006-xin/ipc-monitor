"""Print synthetic 1/4/9-camera analysis baselines as JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.performance_benchmark import (
    run_queue_pressure_benchmark,
    run_synthetic_benchmark,
    run_video_benchmark,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--real", action="store_true", help="run the fixed-video pipeline")
    parser.add_argument("--camera-counts", default="1,4,9",
                        help="comma-separated camera counts for --real (default: 1,4,9)")
    parser.add_argument("--workers", type=int,
                        help="limit concurrent video workers for --real (use 1 on low-memory systems)")
    parser.add_argument("--queue-pressure", action="store_true")
    parser.add_argument("--delay-ms", type=float, default=10)
    args = parser.parse_args()
    if args.queue_pressure:
        print(json.dumps(run_queue_pressure_benchmark(args.frames, args.delay_ms), ensure_ascii=False, indent=2))
        return
    if args.real:
        if args.video is None:
            parser.error("--real requires --video PATH")
        try:
            camera_counts = [int(item.strip()) for item in args.camera_counts.split(",") if item.strip()]
        except ValueError:
            parser.error("--camera-counts must be comma-separated positive integers")
        if not camera_counts or any(item < 1 for item in camera_counts):
            parser.error("--camera-counts must be comma-separated positive integers")
        from core.face_engine import FaceEngine
        from core.motion_engine import MotionEngine
        engine = FaceEngine()
        reports = [run_video_benchmark(
            args.video, camera_count=count, max_frames=args.frames,
            face_engine=engine, motion_engine_factory=MotionEngine,
            face_recognizer=getattr(engine, "recognizer", None),
            max_workers=args.workers,
        ) for count in camera_counts]
    else:
        reports = [run_synthetic_benchmark(camera_count=count, frames_per_camera=args.frames)
                   for count in (1, 4, 9)]
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
