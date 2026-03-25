from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ONCLICK_LOADPAGE_RE = re.compile(r"loadPage\(\s*['\"]([^'\"]+)['\"]")

EXCLUDED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".css",
    ".js",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".pdf",
    ".zip",
}

NOISE_PATTERNS = [
    re.compile(r"^search$", re.IGNORECASE),
    re.compile(r"visit counter", re.IGNORECASE),
    re.compile(r"hitwebcounter", re.IGNORECASE),
    re.compile(r"line", re.IGNORECASE),
]


@dataclass
class PageRow:
    url: str
    title: str
    sections: list[tuple[str, str]]


@dataclass
class ChunkRow:
    doc_id: str
    chunk_id: str
    chunk_index: int
    page_url: str
    page_title: str
    section_title: str
    text: str


def map_repo_url(rel_path: Path) -> str:
    rel = rel_path.as_posix()
    if rel == "index.html":
        return "https://taiwangoldfish.github.io/index/"
    return f"https://taiwangoldfish.github.io/index/{rel}"


def crawl_from_local_repo(repo_dir: Path) -> list[PageRow]:
    pages: list[PageRow] = []
    if not repo_dir.exists() or not repo_dir.is_dir():
        return pages

    html_files = sorted(repo_dir.rglob("*.html"))
    for html_file in html_files:
        rel = html_file.relative_to(repo_dir)
        name = rel.name.lower()
        if name.startswith("google") or name == "uv.html":
            continue
        html = html_file.read_text(encoding="utf-8", errors="ignore")
        title, sections = clean_html_to_sections(html)
        if not sections:
            continue
        pages.append(PageRow(url=map_repo_url(rel), title=title, sections=sections))

    return pages


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    parsed = parsed._replace(fragment="", path=path)
    return urlunparse(parsed)


def has_excluded_extension(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    return any(path.endswith(ext) for ext in EXCLUDED_EXTENSIONS)


def is_allowed(url: str, allowed_domain: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != allowed_domain:
        return False
    if has_excluded_extension(url):
        return False
    return True


def text_is_noise(text: str) -> bool:
    t = text.strip()
    if len(t) <= 1:
        return True
    return any(p.search(t) for p in NOISE_PATTERNS)


def clean_html_to_sections(html: str) -> tuple[str, list[tuple[str, str]]]:
    soup = BeautifulSoup(html, "lxml")

    for tag in ["script", "style", "noscript", "iframe", "header", "footer"]:
        for node in soup.find_all(tag):
            node.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled"

    sections: list[tuple[str, str]] = []
    current_heading = "General"
    current_lines: list[str] = []
    seen: set[str] = set()

    for node in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "label", "button"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if not text or text_is_noise(text):
            continue

        if node.name in {"h1", "h2", "h3"}:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines)))
                current_lines = []
            current_heading = text
            continue

        if text in seen:
            continue
        seen.add(text)
        current_lines.append(text)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines)))

    if not sections:
        fallback_lines: list[str] = []
        seen_fb: set[str] = set()
        for s in soup.stripped_strings:
            text = re.sub(r"\s+", " ", str(s)).strip()
            if not text or text_is_noise(text) or text in seen_fb:
                continue
            seen_fb.add(text)
            fallback_lines.append(text)
        if fallback_lines:
            sections = [("Page Content", "\n".join(fallback_lines))]

    return title, sections


def split_long_text(text: str, max_len: int, overlap: int) -> list[str]:
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        chunk = text[start:end].strip()
        if chunk:
            parts.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return parts


def chunk_sections(page_url: str, page_title: str, sections: list[tuple[str, str]], max_len: int, overlap: int) -> list[ChunkRow]:
    doc_id = hashlib.sha1(page_url.encode("utf-8")).hexdigest()
    rows: list[ChunkRow] = []
    idx = 0

    for section_title, content in sections:
        content = content.strip()
        if not content:
            continue
        for seg in split_long_text(content, max_len=max_len, overlap=overlap):
            idx += 1
            rows.append(
                ChunkRow(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id[:8]}-{idx:04d}",
                    chunk_index=idx,
                    page_url=page_url,
                    page_title=page_title,
                    section_title=section_title,
                    text=seg,
                )
            )
    return rows


def crawl_and_extract(start_url: str, allowed_domain: str, max_pages: int, timeout_sec: int, delay_sec: float) -> list[PageRow]:
    session = requests.Session()
    queue: deque[str] = deque([normalize_url(start_url)])
    visited: set[str] = set()
    pages: list[PageRow] = []

    while queue and len(pages) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url, allowed_domain):
            continue

        try:
            resp = session.get(url, timeout=timeout_sec)
        except requests.RequestException:
            continue

        if resp.status_code != 200:
            time.sleep(delay_sec)
            continue

        html = resp.text
        title, sections = clean_html_to_sections(html)
        if sections:
            pages.append(PageRow(url=url, title=title, sections=sections))

        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            candidate = normalize_url(urljoin(url, a["href"]))
            if candidate not in visited and is_allowed(candidate, allowed_domain):
                queue.append(candidate)

            onclick = a.get("onclick", "")
            m = ONCLICK_LOADPAGE_RE.search(onclick)
            if m:
                sub = normalize_url(urljoin(url, m.group(1)))
                if sub not in visited and is_allowed(sub, allowed_domain):
                    queue.append(sub)

        time.sleep(delay_sec)

    return pages


def save_outputs(pages: list[PageRow], out_dir: Path, max_len: int, overlap: int) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_path = out_dir / "documents.jsonl"
    chunks_path = out_dir / "chunks.jsonl"

    total_chunks = 0
    now = datetime.now(timezone.utc).isoformat()

    with docs_path.open("w", encoding="utf-8") as d_writer, chunks_path.open("w", encoding="utf-8") as c_writer:
        for p in pages:
            doc_id = hashlib.sha1(p.url.encode("utf-8")).hexdigest()
            combined = "\n\n".join([f"## {h}\n{b}" for h, b in p.sections])

            d_writer.write(
                json.dumps(
                    {
                        "doc_id": doc_id,
                        "page_url": p.url,
                        "page_title": p.title,
                        "crawl_timestamp": now,
                        "text": combined,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

            chunks = chunk_sections(p.url, p.title, p.sections, max_len=max_len, overlap=overlap)
            for ch in chunks:
                c_writer.write(
                    json.dumps(
                        {
                            "doc_id": ch.doc_id,
                            "chunk_id": ch.chunk_id,
                            "chunk_index": ch.chunk_index,
                            "page_url": ch.page_url,
                            "page_title": ch.page_title,
                            "section_title": ch.section_title,
                            "text": ch.text,
                            "text_length": len(ch.text),
                            "crawl_timestamp": now,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            total_chunks += len(chunks)

    return {
        "documents": len(pages),
        "chunks": total_chunks,
        "documents_file": str(docs_path).replace("\\", "/"),
        "chunks_file": str(chunks_path).replace("\\", "/"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Learn site content using requests + BeautifulSoup")
    parser.add_argument("--start-url", default="https://taiwangoldfish.github.io/index/")
    parser.add_argument("--allowed-domain", default="taiwangoldfish.github.io")
    parser.add_argument("--max-pages", type=int, default=1200)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--out-dir", type=Path, default=Path("data/learn_requests_bs4"))
    parser.add_argument("--max-chunk-chars", type=int, default=1200)
    parser.add_argument("--overlap-chars", type=int, default=120)
    parser.add_argument("--repo-dir", type=Path, default=Path("index_repo"))
    parser.add_argument("--prefer-local-repo", action="store_true")
    args = parser.parse_args()

    if args.prefer_local_repo:
        pages = crawl_from_local_repo(args.repo_dir)
    else:
        pages = crawl_and_extract(
            start_url=args.start_url,
            allowed_domain=args.allowed_domain,
            max_pages=args.max_pages,
            timeout_sec=args.timeout,
            delay_sec=args.delay,
        )
    summary = save_outputs(
        pages=pages,
        out_dir=args.out_dir,
        max_len=args.max_chunk_chars,
        overlap=args.overlap_chars,
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
