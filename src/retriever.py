from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ZH_RE = re.compile(r"[\u4e00-\u9fff]+")
EN_RE = re.compile(r"[a-z0-9]+")
QUERY_STOP_TOKENS = {
    "什麼",
    "為什",
    "為什麼",
    "為何",
    "如何",
    "多少",
    "可以",
    "建議",
    "比較",
    "較好",
    "好嗎",
    "時候",
    "哪裡",
}


@dataclass
class ChunkItem:
    chunk_id: str
    page_title: str
    page_url: str
    section_title: str
    text: str


@dataclass
class RetrievedItem:
    item: ChunkItem
    score: float


def _tokenize_zh_block(text: str) -> list[str]:
    if len(text) <= 1:
        return [text]
    tokens = [text[i : i + 2] for i in range(len(text) - 1)]
    if len(text) >= 3:
        tokens.extend(text[i : i + 3] for i in range(len(text) - 2))
    return tokens


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = []

    for block in ZH_RE.findall(lowered):
        tokens.extend(_tokenize_zh_block(block))

    tokens.extend(EN_RE.findall(lowered))
    return [t for t in tokens if t]


def load_chunks_jsonl(path: Path) -> list[ChunkItem]:
    if not path.exists():
        raise FileNotFoundError(f"Chunk file not found: {path}")

    items: list[ChunkItem] = []
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            if str(row.get("section_title", "")).strip() == "Image OCR":
                continue
            if _is_navigation_chunk(text):
                continue
            if _is_low_signal_chunk(text):
                continue
            items.append(
                ChunkItem(
                    chunk_id=str(row.get("chunk_id", "")),
                    page_title=str(row.get("page_title", "Untitled")),
                    page_url=str(row.get("page_url", "")),
                    section_title=str(row.get("section_title", "General")),
                    text=text,
                )
            )
    return items


def _is_navigation_chunk(text: str) -> bool:
    # Filter out large menu-like content blocks that are not answer evidence.
    return "🏠 首頁" in text and "🐟 入門篇" in text


def _is_low_signal_chunk(text: str) -> bool:
    """Filter short/low-information chunks that hurt retrieval quality."""
    normalized = " ".join(text.split())
    if not normalized:
        return True
    # Common index artifacts such as teaser entries pointing to a video number.
    if "小影片" in normalized and len(normalized) <= 40:
        return True
    return False


class BM25Retriever:
    def __init__(self, chunks: Iterable[ChunkItem], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b

        self.doc_tokens: list[list[str]] = []
        self.doc_tf: list[dict[str, int]] = []
        self.doc_len: list[int] = []
        self.df: dict[str, int] = {}

        for item in self.chunks:
            tokens = tokenize(item.text)
            tf: dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_tokens.append(tokens)
            self.doc_tf.append(tf)
            self.doc_len.append(len(tokens))
            for token in tf.keys():
                self.df[token] = self.df.get(token, 0) + 1

        self.n_docs = len(self.chunks)
        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0

    def _idf(self, token: str) -> float:
        df = self.df.get(token, 0)
        if df == 0:
            return 0.0
        return math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def _score_doc(self, query_tokens: list[str], doc_idx: int) -> float:
        if not query_tokens or self.n_docs == 0:
            return 0.0

        score = 0.0
        tf = self.doc_tf[doc_idx]
        dl = self.doc_len[doc_idx]
        denom_norm = self.k1 * (1 - self.b + self.b * (dl / self.avgdl)) if self.avgdl > 0 else self.k1

        for token in query_tokens:
            f = tf.get(token, 0)
            if f == 0:
                continue
            idf = self._idf(token)
            numer = f * (self.k1 + 1)
            denom = f + denom_norm
            score += idf * (numer / denom)
        return score

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        boost_keywords: list[str] | None = None,
        core_keywords: list[str] | None = None,
    ) -> list[RetrievedItem]:
        query_tokens = tokenize(query)
        filtered_query_tokens = [token for token in query_tokens if token not in QUERY_STOP_TOKENS]
        if filtered_query_tokens:
            query_tokens = filtered_query_tokens
        query_token_set = {token for token in query_tokens if len(token) >= 2}
        scored: list[RetrievedItem] = []
        boost_keywords = boost_keywords or []
        core_keywords = core_keywords or []

        for idx, item in enumerate(self.chunks):
            score = self._score_doc(query_tokens, idx)
            title_text = item.page_title.lower()
            section_text = item.section_title.lower()
            title_and_section = f"{title_text} {section_text}"
            if score > 0 and query_token_set:
                title_token_matches = sum(1 for token in query_token_set if token in title_text)
                section_token_matches = sum(1 for token in query_token_set if token in section_text)
                if title_token_matches > 0:
                    score += 1.5 * title_token_matches
                if section_token_matches > 0:
                    score += 0.25 * section_token_matches
            if score > 0 and core_keywords:
                core_matched = sum(1 for kw in core_keywords if kw and kw in item.text)
                core_matched += sum(1 for kw in core_keywords if kw and kw in title_and_section)
                if core_matched > 0:
                    # Core knowledge receives stronger priority boost, especially
                    # when it matches the page title or section heading.
                    score += 1.0 * core_matched
            if score > 0 and boost_keywords:
                # Extra weight if page chunk contains matched site keywords.
                matched = sum(1 for kw in boost_keywords if kw and kw in item.text)
                matched += sum(1 for kw in boost_keywords if kw and kw in title_and_section)
                if matched > 0:
                    score += 0.5 * matched
            if score <= 0:
                continue
            scored.append(RetrievedItem(item=item, score=score))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]
