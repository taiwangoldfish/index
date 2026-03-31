from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from src.config import PipelineConfig
from src.pipeline import run_pipeline


ZH_BLOCK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
EN_WORD_RE = re.compile(r"[a-zA-Z]{3,}")
EN_STOPWORDS = {
    "the",
    "and",
    "for",
    "are",
    "that",
    "with",
    "from",
    "have",
    "this",
    "your",
    "you",
    "how",
    "why",
    "can",
}


def extract_keywords(chunks_file: Path, top_n: int = 500) -> dict[str, int]:
    keyword_count: Counter[str] = Counter()
    if not chunks_file.exists():
        return {}

    with chunks_file.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = str(row.get("text", ""))
            for match in ZH_BLOCK_RE.finditer(text):
                token = match.group()
                if len(token) <= 20:
                    keyword_count[token] += 1

            for match in EN_WORD_RE.finditer(text):
                token = match.group().lower()
                if token not in EN_STOPWORDS:
                    keyword_count[token] += 1

    return dict(keyword_count.most_common(top_n))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build keyword index from chunks, optionally running the pipeline first")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data"),
        help="Data root containing chunks/ and where keyword_index.json will be written",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "repo", "web"],
        default="auto",
        help="Content source mode if pipeline execution is enabled",
    )
    parser.add_argument("--max-pages", type=int, default=600, help="Maximum pages to crawl when pipeline runs")
    parser.add_argument("--top-n", type=int, default=500, help="Number of keywords to keep")
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip crawl/clean/chunk and build keyword index from existing chunks.jsonl only",
    )
    args = parser.parse_args()

    config = PipelineConfig(
        data_root=args.data_root,
        source_mode=args.source,
        max_pages=args.max_pages,
    )
    config.start_url = "https://taiwangoldfish.github.io/index/"
    # Focus crawl scope on the index site only.
    config.utility_urls = []

    if not args.skip_pipeline:
        print("[1/2] Running pipeline for index site...")
        summary = run_pipeline(config)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("[2/2] Extracting keyword index...")
    else:
        print("[skip] Using existing chunks file...")

    chunks_file = config.chunks_dir / "chunks.jsonl"
    keyword_index = extract_keywords(chunks_file, top_n=args.top_n)

    output_path = config.data_root / "keyword_index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(keyword_index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"keywords_saved={len(keyword_index)}")
    print(f"output={output_path}")
    top10 = list(keyword_index.items())[:10]
    print("top10_keywords=")
    for key, value in top10:
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
