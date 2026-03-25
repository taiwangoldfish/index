from __future__ import annotations

import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .config import PipelineConfig


ONCLICK_LOADPAGE_RE = re.compile(r"loadPage\(\s*['\"]([^'\"]+)['\"]")


@dataclass
class CrawledPage:
    url: str
    html_path: Path
    status_code: int


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="")
    path = normalized.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    normalized = normalized._replace(path=path)
    return urlunparse(normalized)


def _is_same_domain(url: str, config: PipelineConfig) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == config.allowed_domain


def _has_excluded_extension(url: str, config: PipelineConfig) -> bool:
    path = (urlparse(url).path or "").lower()
    return any(path.endswith(ext) for ext in config.excluded_extensions)


def _is_excluded_domain(url: str, config: PipelineConfig) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in config.excluded_domains)


def _is_allowed(url: str, config: PipelineConfig) -> bool:
    if _is_excluded_domain(url, config):
        return False
    if _has_excluded_extension(url, config):
        return False
    return _is_same_domain(url, config)


def _url_to_filename(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"{digest}.html"


def crawl_site(config: PipelineConfig) -> list[CrawledPage]:
    session = requests.Session()
    config.raw_dir.mkdir(parents=True, exist_ok=True)

    queue: deque[str] = deque()
    queue.append(_normalize_url(config.start_url))
    for utility_url in config.utility_urls:
        queue.append(_normalize_url(utility_url))

    visited: set[str] = set()
    crawled: list[CrawledPage] = []

    while queue and len(crawled) < config.max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not _is_allowed(url, config):
            continue

        try:
            response = session.get(url, timeout=config.request_timeout_seconds)
        except requests.RequestException:
            continue

        html_filename = _url_to_filename(url)
        html_path = config.raw_dir / html_filename
        html_path.write_text(response.text, encoding="utf-8", errors="ignore")

        crawled.append(CrawledPage(url=url, html_path=html_path, status_code=response.status_code))

        if response.status_code != 200:
            time.sleep(config.crawl_delay_seconds)
            continue

        soup = BeautifulSoup(response.text, "lxml")
        for anchor in soup.find_all("a", href=True):
            candidate = _normalize_url(urljoin(url, anchor["href"]))
            if candidate in visited:
                continue
            if _is_allowed(candidate, config):
                queue.append(candidate)

            onclick_value = anchor.get("onclick", "")
            match = ONCLICK_LOADPAGE_RE.search(onclick_value)
            if not match:
                continue
            subpage_url = _normalize_url(urljoin(url, match.group(1)))
            if subpage_url in visited:
                continue
            if _is_allowed(subpage_url, config):
                queue.append(subpage_url)

        time.sleep(config.crawl_delay_seconds)

    return crawled
