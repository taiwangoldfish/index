from __future__ import annotations

import argparse
from pathlib import Path

from src.reporting import generate_daily_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily tuning report from interaction logs")
    parser.add_argument("--date", type=str, default=None, help="Target date in YYYY-MM-DD (UTC)")
    parser.add_argument("--log-file", type=Path, default=Path("data/logs/interactions.jsonl"))
    parser.add_argument("--report-dir", type=Path, default=Path("data/reports"))
    args = parser.parse_args()

    result = generate_daily_report(args.log_file, args.report_dir, target_date=args.date)
    print(f"date={result.date}")
    print(f"markdown={result.markdown_path}")
    print(f"csv={result.csv_path}")
    print(f"total_asks={result.total_asks}")
    print(f"low_confidence_count={result.low_confidence_count}")
    print(f"down_feedback_count={result.down_feedback_count}")


if __name__ == "__main__":
    main()
