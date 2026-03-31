import argparse
from pprint import pprint
from pathlib import Path

from src.config import PipelineConfig
from src.pipeline import run_pipeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run crawl/clean/chunk pipeline")
    parser.add_argument(
        "--source",
        choices=["auto", "repo", "web"],
        default="auto",
        help="Content source mode: repo snapshot, live web crawl, or auto fallback",
    )
    parser.add_argument("--max-pages", type=int, default=300, help="Maximum pages to crawl in web mode")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Delay between requests in seconds when crawling the web",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Per-request timeout in seconds when crawling the web",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data"),
        help="Output directory for raw/clean/chunks/ocr artifacts",
    )
    args = parser.parse_args()

    config = PipelineConfig(
        source_mode=args.source,
        max_pages=args.max_pages,
        crawl_delay_seconds=args.delay,
        request_timeout_seconds=args.timeout,
        data_root=args.data_root,
    )
    summary = run_pipeline(config)
    pprint(summary)
