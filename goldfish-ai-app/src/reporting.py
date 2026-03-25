from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


LOW_CONFIDENCE_THRESHOLD = 0.35


@dataclass
class DailyReportResult:
    date: str
    markdown_path: Path
    csv_path: Path
    total_asks: int
    low_confidence_count: int
    down_feedback_count: int


def _read_logs(log_file: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not log_file.exists():
        return [], []

    asks: list[dict[str, object]] = []
    feedbacks: list[dict[str, object]] = []

    with log_file.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            row_type = row.get("type")
            if row_type == "ask":
                asks.append(row)
            elif row_type == "feedback":
                feedbacks.append(row)

    return asks, feedbacks


def _extract_date(timestamp: str) -> str:
    if not timestamp:
        return ""
    return timestamp[:10]


def _today_utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def generate_daily_report(log_file: Path, report_dir: Path, *, target_date: str | None = None) -> DailyReportResult:
    asks, feedbacks = _read_logs(log_file)
    date_key = target_date or _today_utc_date()

    feedback_map: dict[str, dict[str, str]] = {}
    for fb in feedbacks:
        iid = str(fb.get("interaction_id", ""))
        if not iid:
            continue
        feedback_map[iid] = {
            "rating": str(fb.get("rating", "")),
            "comment": str(fb.get("comment", "")),
        }

    rows: list[dict[str, object]] = []
    source_counter: dict[str, int] = {}
    low_confidence_count = 0
    down_feedback_count = 0

    for ask in asks:
        ts = str(ask.get("timestamp", ""))
        if _extract_date(ts) != date_key:
            continue

        iid = str(ask.get("interaction_id", ""))
        question = str(ask.get("question", ""))
        conclusion = str(ask.get("conclusion", ""))
        confidence = float(ask.get("confidence", 0.0) or 0.0)
        source_urls = [str(x) for x in ask.get("source_urls", [])]

        fb = feedback_map.get(iid, {"rating": "", "comment": ""})
        rating = fb.get("rating", "")
        comment = fb.get("comment", "")

        is_low = confidence < LOW_CONFIDENCE_THRESHOLD
        is_down = rating == "down"
        if is_low:
            low_confidence_count += 1
        if is_down:
            down_feedback_count += 1

        if is_low or is_down:
            for url in source_urls:
                source_counter[url] = source_counter.get(url, 0) + 1

        rows.append(
            {
                "timestamp": ts,
                "interaction_id": iid,
                "question": question,
                "conclusion": conclusion,
                "confidence": round(confidence, 3),
                "rating": rating,
                "comment": comment,
                "source_urls": " | ".join(source_urls),
            }
        )

    report_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = report_dir / f"daily-report-{date_key}.md"
    csv_path = report_dir / f"daily-report-{date_key}.csv"

    sorted_sources = sorted(source_counter.items(), key=lambda x: x[1], reverse=True)

    md_lines = [
        f"# Daily Tuning Report {date_key}",
        "",
        f"- Total asks: {len(rows)}",
        f"- Low confidence (< {LOW_CONFIDENCE_THRESHOLD}): {low_confidence_count}",
        f"- Down feedback: {down_feedback_count}",
        "",
        "## Priority Source Pages",
    ]

    if sorted_sources:
        for idx, (url, count) in enumerate(sorted_sources[:20], start=1):
            md_lines.append(f"{idx}. {url} (issues: {count})")
    else:
        md_lines.append("No source pages flagged today.")

    md_lines.extend(["", "## Notes", "- Prioritize pages with repeated low confidence/down feedback."])
    markdown_path.write_text("\n".join(md_lines), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as writer_file:
        writer = csv.DictWriter(
            writer_file,
            fieldnames=["timestamp", "interaction_id", "question", "conclusion", "confidence", "rating", "comment", "source_urls"],
        )
        writer.writeheader()
        writer.writerows(rows)

    latest_md = report_dir / "daily-report-latest.md"
    latest_csv = report_dir / "daily-report-latest.csv"
    latest_md.write_text(markdown_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_csv.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")

    return DailyReportResult(
        date=date_key,
        markdown_path=markdown_path,
        csv_path=csv_path,
        total_asks=len(rows),
        low_confidence_count=low_confidence_count,
        down_feedback_count=down_feedback_count,
    )
