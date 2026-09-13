"""Print synthetic 1/4/9-camera analysis baselines as JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.performance_benchmark import run_synthetic_benchmark


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()
    reports = [
        run_synthetic_benchmark(camera_count=count, frames_per_camera=args.frames)
        for count in (1, 4, 9)
    ]
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
