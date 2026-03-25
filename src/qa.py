from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .retriever import BM25Retriever, RetrievedItem, load_chunks_jsonl


NOT_FOUND_TEXT = "目前資料中找不到足夠資訊回答此問題。"
MIN_CONFIDENCE = 0.35


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

    @classmethod
    def from_chunk_file(cls, chunk_file: Path) -> "QAEngine":
        chunks = load_chunks_jsonl(chunk_file)
        retriever = BM25Retriever(chunks)
        return cls(retriever=retriever)

    def answer_result(self, question: str, top_k: int = 5) -> "QAResult":
        hits = self.retriever.retrieve(question, top_k=top_k)
        if not hits:
            response = QAResponse(
                conclusion=NOT_FOUND_TEXT,
                evidence=["無符合證據片段。"],
                sources=[],
                confidence=0.0,
            )
            return QAResult(response=response, retrieved_chunk_ids=[], top_score=0.0)

        top_score = hits[0].score
        confidence = _score_to_confidence(top_score)
        if confidence < MIN_CONFIDENCE:
            response = QAResponse(
                conclusion=NOT_FOUND_TEXT,
                evidence=["檢索到的證據相關性不足。"],
                sources=[],
                confidence=confidence,
            )
            return QAResult(
                response=response,
                retrieved_chunk_ids=[h.item.chunk_id for h in hits],
                top_score=top_score,
            )

        conclusion = _build_conclusion(hits)
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


def _score_to_confidence(score: float) -> float:
    # Convert BM25 score into [0, 1] for UI and gating.
    if score <= 0:
        return 0.0
    confidence = score / (score + 3.0)
    return max(0.0, min(1.0, confidence))


def _first_sentence(text: str, max_len: int = 140) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[:max_len].rstrip() + "..."


def _build_conclusion(hits: list[RetrievedItem]) -> str:
    top = hits[0].item
    return _first_sentence(top.text)


def _build_evidence(hits: list[RetrievedItem]) -> list[str]:
    lines: list[str] = []
    for i, hit in enumerate(hits[:3], start=1):
        snippet = _first_sentence(hit.item.text, max_len=120)
        lines.append(snippet)
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
