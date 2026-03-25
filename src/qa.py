from __future__ import annotations

import json
import re
import unicodedata as _ud
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .retriever import BM25Retriever, RetrievedItem, load_chunks_jsonl, tokenize
from .learning_profile import load_learning_profile
from .llm_enhancer import enhance_conclusion


NOT_FOUND_TEXT = "目前資料中找不到足夠資訊回答此問題。"
MIN_CONFIDENCE = 0.35
ZH_BLOCK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
EN_WORD_RE = re.compile(r"[a-zA-Z0-9]{2,}")
ZH_ONLY_RE = re.compile(r"^[\u4e00-\u9fff]+$")


@dataclass
class SourceRef:
    title: str
    section: str
    url: str


@dataclass
class QAResponse:
    conclusion: str
    evidence: list[str]
    sources: list[SourceRef]
    confidence: float

    def to_text(self) -> str:
        evidence_lines = [f"- [{i}] {line}" for i, line in enumerate(self.evidence, start=1)]
        source_lines: list[str] = []
        for i, source in enumerate(self.sources, start=1):
            source_lines.append(f"- [來源 {i}] {source.title} / {source.section}")
            source_lines.append(f"  URL: {source.url}")

        if not source_lines:
            source_lines = ["- 無"]

        return "\n".join([
            f"結論: {self.conclusion}",
            f"信心: {self.confidence:.2f}",
            "依據:",
            *evidence_lines,
            "來源:",
            *source_lines,
        ])


@dataclass
class QAEngine:
    retriever: BM25Retriever
    site_keywords: list[tuple[str, int]]
    core_keywords: list[str]

    @classmethod
    def from_chunk_file(cls, chunk_file: Path) -> "QAEngine":
        chunks = load_chunks_jsonl(chunk_file)
        retriever = BM25Retriever(chunks)
        keyword_file = chunk_file.parent.parent / "keyword_index.json"
        site_keywords = _load_site_keywords(keyword_file)
        learning_profile_path = chunk_file.parent.parent / "learning_profile.json"
        learning_profile = load_learning_profile(learning_profile_path)
        core_keywords = [str(x) for x in learning_profile.get("core_keywords", []) if str(x).strip()]
        return cls(retriever=retriever, site_keywords=site_keywords, core_keywords=core_keywords)

    def answer_result(self, question: str, top_k: int = 5) -> "QAResult":
        core_keyword_pairs = [(k, 100) for k in self.core_keywords]
        matched_core_keywords = _match_site_keywords(question, core_keyword_pairs, max_terms=20)
        matched_keywords = _match_site_keywords(question, self.site_keywords, max_terms=40)
        boost_keywords = matched_keywords[:12]
        core_boost_keywords = matched_core_keywords[:8]
        hits = self.retriever.retrieve(
            question,
            top_k=top_k,
            boost_keywords=boost_keywords,
            core_keywords=core_boost_keywords,
        )
        merged_keywords = list(dict.fromkeys([*matched_core_keywords, *matched_keywords]))
        if not hits:
            response = QAResponse(
                conclusion=NOT_FOUND_TEXT,
                evidence=["無符合證據片段。"],
                sources=[],
                confidence=0.0,
            )
            return QAResult(response=response, retrieved_chunk_ids=[], top_score=0.0, matched_keywords=merged_keywords)

        top_score = hits[0].score
        confidence = _score_to_confidence(top_score)
        if confidence < MIN_CONFIDENCE:
            tentative = _build_tentative_conclusion(hits)
            tentative = enhance_conclusion(question, hits, tentative)
            response = QAResponse(
                conclusion=tentative,
                evidence=_build_evidence(hits),
                sources=_build_sources(hits),
                confidence=confidence,
            )
            return QAResult(
                response=response,
                retrieved_chunk_ids=[h.item.chunk_id for h in hits],
                top_score=top_score,
                matched_keywords=merged_keywords,
            )

        conclusion = _build_conclusion(hits)
        conclusion = enhance_conclusion(question, hits, conclusion)
        evidence_lines = _build_evidence(hits)
        sources = _build_sources(hits)

        response = QAResponse(
            conclusion=conclusion,
            evidence=evidence_lines,
            sources=sources,
            confidence=confidence,
        )
        return QAResult(
            response=response,
            retrieved_chunk_ids=[h.item.chunk_id for h in hits],
            top_score=top_score,
            matched_keywords=merged_keywords,
        )

    def answer_structured(self, question: str, top_k: int = 5) -> QAResponse:
        return self.answer_result(question, top_k=top_k).response

    def answer(self, question: str, top_k: int = 5) -> str:
        response = self.answer_structured(question, top_k=top_k)
        return response.to_text()


@dataclass
class QAResult:
    response: QAResponse
    retrieved_chunk_ids: list[str]
    top_score: float
    matched_keywords: list[str]


def _load_site_keywords(path: Path, min_freq: int = 2) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as reader:
            data = json.load(reader)
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    items: list[tuple[str, int]] = []
    expanded: dict[str, int] = {}
    generic_zh_stop = {
        "為什麼",
        "注意事項",
        "建議",
        "方式",
        "使用",
        "操作",
        "圖示",
        "分享",
        "介紹",
    }
    for k, v in data.items():
        kw = str(k).strip()
        if not kw or len(kw) < 2:
            continue
        try:
            freq = int(v)
        except Exception:
            freq = 0
        if freq < min_freq:
            continue
        if kw in {"小影片", "影片", "https", "csv", "top", "max"}:
            continue
        items.append((kw, freq))

        # Expand long Chinese phrases into shorter sub-phrases for better recall.
        if ZH_ONLY_RE.match(kw) and len(kw) >= 4:
            max_n = min(6, len(kw))
            for n in range(2, max_n + 1):
                for i in range(0, len(kw) - n + 1):
                    sub = kw[i : i + n]
                    if sub in generic_zh_stop:
                        continue
                    if len(sub) < 2:
                        continue
                    expanded[sub] = expanded.get(sub, 0) + max(1, freq // 3)

    for sub, freq in expanded.items():
        if freq < min_freq:
            continue
        items.append((sub, freq))

    items.sort(key=lambda x: (x[1], len(x[0])), reverse=True)
    # Deduplicate and keep highest frequency per keyword.
    merged: dict[str, int] = {}
    for kw, freq in items:
        prev = merged.get(kw, 0)
        if freq > prev:
            merged[kw] = freq
    merged_items = sorted(merged.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
    return merged_items


def _match_site_keywords(question: str, site_keywords: list[tuple[str, int]], max_terms: int = 15) -> list[str]:
    q = " ".join(question.split()).lower()
    if not q or not site_keywords:
        return []

    zh_blocks = [b for b in ZH_BLOCK_RE.findall(q) if len(b) >= 2]
    en_words = [w for w in EN_WORD_RE.findall(q) if len(w) >= 2]
    query_tokens = list(dict.fromkeys(tokenize(q)))

    scored: list[tuple[float, str, int]] = []
    for kw, freq in site_keywords:
        k = kw.lower()
        score = 0.0

        if k in q:
            score += 120.0 + min(len(k), 10)

        for block in zh_blocks:
            if block in k:
                score += 55.0 + min(len(block), 8)
            if k in block:
                score += 90.0 + min(len(k), 8)

        for word in en_words:
            if word in k:
                score += 25.0

        for t in query_tokens:
            if len(t) >= 2 and t in k:
                score += 3.0

        if score <= 0:
            continue

        score += min(freq, 25) * 0.6
        scored.append((score, kw, freq))

    scored.sort(key=lambda x: (x[0], x[2], len(x[1])), reverse=True)
    return [kw for _, kw, _ in scored[:max_terms]]


def _score_to_confidence(score: float) -> float:
    # Convert BM25 score into [0, 1] for UI and gating.
    if score <= 0:
        return 0.0
    confidence = score / (score + 3.0)
    return max(0.0, min(1.0, confidence))


def _is_title_line(line: str) -> bool:
    """Return True if the line looks like an emoji/section-header title with no real content."""
    stripped = line.strip()
    if not stripped:
        return True
    if len(stripped) <= 40:
        emoji_count = sum(1 for ch in stripped if _ud.category(ch) in ('So', 'Sm') or ord(ch) > 0x1F000)
        if emoji_count > 0:
            return True
    return False


def _source_hint(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "來源"
    return path.split("/")[-1].replace(".html", "") or "來源"


def _best_content_line(text: str) -> str:
    """Pick a meaningful content line instead of title/emoji headers."""
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if _is_title_line(line):
            continue
        if "小影片" in line and len(line) <= 40:
            continue
        if len(line) < 8:
            continue
        return line
    return ""

def _first_sentence(text: str, max_len: int = 140) -> str:
    first = _best_content_line(text)
    if first:
        cleaned = first
    else:
        cleaned = " ".join(text.split())
    if not cleaned:
        cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip() + "..."


def _build_conclusion(hits: list[RetrievedItem]) -> str:
    top = hits[0].item
    first = _first_sentence(top.text, max_len=120)
    if len(first) >= 16:
        return first
    if len(hits) > 1:
        second = _first_sentence(hits[1].item.text, max_len=120)
        if second:
            return second
    return first or "已找到相關資料，請先參考下方段落與來源。"


def _build_tentative_conclusion(hits: list[RetrievedItem]) -> str:
    top = hits[0].item
    base = _first_sentence(top.text)
    return f"根據目前可檢索資料，{base}（此答案可能不完整，建議搭配下方來源查看原文）"


def _build_evidence(hits: list[RetrievedItem]) -> list[str]:
    lines: list[str] = []
    for i, hit in enumerate(hits[:4], start=1):
        snippet = _first_sentence(hit.item.text, max_len=120)
        hint = _source_hint(hit.item.page_url)
        lines.append(f"[{hint}] {snippet}")
    return lines


def _build_sources(hits: list[RetrievedItem]) -> list[SourceRef]:
    refs: list[SourceRef] = []
    seen: set[tuple[str, str]] = set()
    source_idx = 0

    for hit in hits:
        key = (hit.item.page_title, hit.item.page_url)
        if key in seen:
            continue
        seen.add(key)
        source_idx += 1
        refs.append(SourceRef(title=hit.item.page_title, section=hit.item.section_title, url=hit.item.page_url))
        if source_idx >= 3:
            break

    return refs
