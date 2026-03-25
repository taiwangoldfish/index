from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from bs4 import BeautifulSoup


NOISE_LINE_PATTERNS = [
    re.compile(r"^☰\s*選單$", re.IGNORECASE),
    re.compile(r"^搜尋$", re.IGNORECASE),
    re.compile(r"LINE 社群", re.IGNORECASE),
    re.compile(r"Visit counter", re.IGNORECASE),
    re.compile(r"點我加入", re.IGNORECASE),
    re.compile(r"QR Code", re.IGNORECASE),
    re.compile(r"累積造訪人數", re.IGNORECASE),
    re.compile(r"hitwebcounter", re.IGNORECASE),
    re.compile(r"^©"),
]


@dataclass
class CleanedPage:
    url: str
    title: str
    clean_text_path: Path
    sections: list[tuple[str, str]]


def _is_noise_line(line: str) -> bool:
    normalized = line.strip()
    if not normalized:
        return True
    if len(normalized) <= 1:
        return True
    return any(pattern.search(normalized) for pattern in NOISE_LINE_PATTERNS)


def _normalize_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def clean_html_to_sections(html_text: str) -> tuple[str, list[tuple[str, str]]]:
    soup = BeautifulSoup(html_text, "lxml")

    for tag_name in ["script", "style", "noscript", "iframe", "header", "footer"]:
        for node in soup.find_all(tag_name):
            node.decompose()

    title = (soup.title.string.strip() if soup.title and soup.title.string else "Untitled")

    sections: list[tuple[str, str]] = []
    current_heading = "General"
    current_lines: list[str] = []
    seen_lines: set[str] = set()

    for node in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "label", "button"]):
        text = _normalize_line(node.get_text(" ", strip=True))
        if _is_noise_line(text):
            continue

        if node.name in {"h1", "h2", "h3"}:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines)))
                current_lines = []
            current_heading = text
            continue

        if text in seen_lines:
            continue
        seen_lines.add(text)
        current_lines.append(text)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines)))

    # If extraction is too sparse, fall back to visible body strings.
    total_chars = sum(len(content) for _, content in sections)
    if len(sections) <= 1 or total_chars < 400:
        fallback_lines: list[str] = []
        seen_fallback: set[str] = set()
        for text in soup.stripped_strings:
            normalized = _normalize_line(text)
            if _is_noise_line(normalized):
                continue
            if normalized in seen_fallback:
                continue
            seen_fallback.add(normalized)
            fallback_lines.append(normalized)

        if fallback_lines:
            sections = [("Page Content", "\n".join(fallback_lines))]

    filtered_sections = [(h, c) for h, c in sections if c.strip()]
    return title, filtered_sections


def write_clean_text(clean_dir: Path, source_url: str, title: str, sections: list[tuple[str, str]]) -> Path:
    clean_dir.mkdir(parents=True, exist_ok=True)

    file_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", source_url).strip("_")
    file_name = f"{file_stem[:120]}.md"
    output_path = clean_dir / file_name

    lines = [f"# {title}", f"Source: {source_url}", ""]
    for heading, body in sections:
        lines.append(f"## {heading}")
        lines.append(body)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
