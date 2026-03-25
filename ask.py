from __future__ import annotations

import argparse
from pathlib import Path

from src.qa import QAEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask question against local chunks.jsonl")
    parser.add_argument("question", type=str, help="Question in Traditional Chinese")
    parser.add_argument(
        "--chunk-file",
        type=Path,
        default=Path("data/chunks/chunks.jsonl"),
        help="Path to chunk JSONL file",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieval results")
    args = parser.parse_args()

    engine = QAEngine.from_chunk_file(args.chunk_file)
    answer = engine.answer(args.question, top_k=args.top_k)
    print(answer)


if __name__ == "__main__":
    main()
