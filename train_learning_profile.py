from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.learning_profile import build_learning_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Build learning profile from keyword index and interaction logs")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data"),
        help="Data root containing keyword_index.json, logs/, and learning_profile.json",
    )
    args = parser.parse_args()

    data_root = args.data_root
    keyword_index_path = data_root / "keyword_index.json"
    interactions_path = data_root / "logs" / "interactions.jsonl"
    output_path = data_root / "learning_profile.json"

    profile = build_learning_profile(
        keyword_index_path=keyword_index_path,
        interactions_path=interactions_path,
        output_path=output_path,
        core_size=40,
        secondary_size=260,
    )
    print(json.dumps({
        "data_root": str(data_root).replace("\\", "/"),
        "output": str(output_path).replace("\\", "/"),
        "core_keywords": len(profile.get("core_keywords", [])),
        "secondary_keywords": len(profile.get("secondary_keywords", [])),
        "up_terms": int((profile.get("stats") or {}).get("up_term_count", 0)),
        "down_terms": int((profile.get("stats") or {}).get("down_term_count", 0)),
        "trained_runs": int(profile.get("trained_runs", 0)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
