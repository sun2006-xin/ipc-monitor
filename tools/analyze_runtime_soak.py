"""Summarize a privacy-safe IPC-Monitor runtime soak CSV."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.runtime_soak import assess_soak_summary, summarize_soak_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="run_runtime_soak.py 输出的 CSV")
    args = parser.parse_args(argv)
    try:
        summary = summarize_soak_csv(args.csv_path)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    summary.update(assess_soak_summary(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
