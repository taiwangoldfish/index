from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import PipelineConfig


@dataclass
class RepoPage:
    url: str
    html_path: Path
    status_code: int


def _is_html_file(path: Path) -> bool:
    return path.suffix.lower() == ".html"


def _is_excluded_file(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("google") or name == "uv.html"


def _relative_web_url(rel_path: Path) -> str:
    rel = rel_path.as_posix()
    if rel == "index.html":
        return "https://taiwangoldfish.github.io/index/"
    return f"https://taiwangoldfish.github.io/index/{rel}"


def load_repo_pages(config: PipelineConfig) -> list[RepoPage]:
    if config.source_repo_dir is None:
        return []

    repo_dir = config.source_repo_dir
    if not repo_dir.exists() or not repo_dir.is_dir():
        return []

    pages: list[RepoPage] = []
    html_files = sorted(repo_dir.rglob("*.html"))

    for html_file in html_files:
        rel_path = html_file.relative_to(repo_dir)
        if _is_excluded_file(rel_path):
            continue
        if not _is_html_file(rel_path):
            continue

        pages.append(
            RepoPage(
                url=_relative_web_url(rel_path),
                html_path=html_file,
                status_code=200,
            )
        )

    return pages
