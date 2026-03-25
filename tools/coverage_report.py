from __future__ import annotations

import json
from pathlib import Path


def build_repo_urls(repo_dir: Path) -> list[str]:
    urls: list[str] = []
    for html_file in sorted(repo_dir.rglob("*.html")):
        name = html_file.name.lower()
        if name.startswith("google") or name == "uv.html":
            continue
        rel = html_file.relative_to(repo_dir).as_posix()
        if rel == "index.html":
            urls.append("https://taiwangoldfish.github.io/index/")
        else:
            urls.append(f"https://taiwangoldfish.github.io/index/{rel}")
    return urls


def load_indexed_urls(docs_jsonl: Path) -> set[str]:
    urls: set[str] = set()
    if not docs_jsonl.exists():
        return urls
    with docs_jsonl.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            page_url = str(row.get("page_url", "")).strip()
            if page_url:
                urls.add(page_url)
    return urls


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    repo_dir = root / "index_repo"
    docs_jsonl = root / "data" / "chunks" / "documents.jsonl"
    out_path = root / "data" / "index_coverage_report.json"

    repo_urls = build_repo_urls(repo_dir)
    repo_set = set(repo_urls)
    indexed_set = load_indexed_urls(docs_jsonl)

    missing = sorted(repo_set - indexed_set)
    extra = sorted(indexed_set - repo_set)

    report = {
        "repo_html_total": len(repo_urls),
        "indexed_docs_total": len(indexed_set),
        "missing_in_index_total": len(missing),
        "extra_in_index_total": len(extra),
        "missing_in_index": missing,
        "extra_in_index": extra,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={out_path}")
    print(f"repo_html_total={len(repo_urls)}")
    print(f"indexed_docs_total={len(indexed_set)}")
    print(f"missing_in_index_total={len(missing)}")
    print(f"extra_in_index_total={len(extra)}")


if __name__ == "__main__":
    main()
