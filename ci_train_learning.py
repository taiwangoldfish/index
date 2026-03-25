from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from src.cleaner import clean_html_to_sections
from src.learning_profile import build_learning_profile


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


def _extract_keywords_from_repo(repo_dir: Path, top_n: int = 500) -> dict[str, int]:
    counter: Counter[str] = Counter()
    if not repo_dir.exists() or not repo_dir.is_dir():
        return {}

    for html_file in sorted(repo_dir.rglob("*.html")):
        name = html_file.name.lower()
        if name.startswith("google") or name == "uv.html":
            continue

        html = html_file.read_text(encoding="utf-8", errors="ignore")
        _, sections = clean_html_to_sections(html)
        for _, text in sections:
            for m in ZH_BLOCK_RE.finditer(text):
                token = m.group()
                if len(token) <= 20:
                    counter[token] += 1

            for m in EN_WORD_RE.finditer(text):
                token = m.group().lower()
                if token not in EN_STOPWORDS:
                    counter[token] += 1

    return dict(counter.most_common(top_n))


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    repo_dir = root / "index_repo"

    data_dir.mkdir(parents=True, exist_ok=True)

    keyword_index = _extract_keywords_from_repo(repo_dir, top_n=500)
    keyword_path = data_dir / "keyword_index.json"
    keyword_path.write_text(json.dumps(keyword_index, ensure_ascii=False, indent=2), encoding="utf-8")

    profile = build_learning_profile(
        keyword_index_path=keyword_path,
        interactions_path=data_dir / "logs" / "interactions.jsonl",
        output_path=data_dir / "learning_profile.json",
        core_size=40,
        secondary_size=260,
    )

    summary = {
        "repo_dir": str(repo_dir).replace("\\", "/"),
        "keyword_count": len(keyword_index),
        "core_keywords": len(profile.get("core_keywords", [])),
        "secondary_keywords": len(profile.get("secondary_keywords", [])),
        "trained_runs": int(profile.get("trained_runs", 0)),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
