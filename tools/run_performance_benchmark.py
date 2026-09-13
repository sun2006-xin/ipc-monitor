"""Print synthetic 1/4/9-camera analysis baselines as JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.performance_benchmark import run_synthetic_benchmark, run_video_benchmark


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--real", action="store_true", help="run the fixed-video pipeline")
    args = parser.parse_args()
    if args.real:
        if args.video is None:
            parser.error("--real requires --video PATH")
        from core.face_engine import FaceEngine
        from core.motion_engine import MotionEngine
        engine = FaceEngine()
        reports = [run_video_benchmark(
            args.video, camera_count=count, max_frames=args.frames,
            face_engine=engine, motion_engine_factory=MotionEngine,
            face_recognizer=getattr(engine, "recognizer", None),
        ) for count in (1, 4, 9)]
    else:
        reports = [run_synthetic_benchmark(camera_count=count, frames_per_camera=args.frames)
                   for count in (1, 4, 9)]
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
