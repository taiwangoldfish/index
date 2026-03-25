from __future__ import annotations

from dataclasses import dataclass

from .config import PipelineConfig


@dataclass
class ChunkRecord:
    chunk_id: str
    chunk_index: int
    section_title: str
    text: str
    text_length: int


def _split_long_text(text: str, max_len: int, overlap: int) -> list[str]:
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def chunk_sections(doc_prefix: str, sections: list[tuple[str, str]], config: PipelineConfig) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    chunk_index = 0

    for section_title, section_text in sections:
        text = section_text.strip()
        if not text:
            continue

        if len(text) < config.min_chunk_chars:
            segment_list = [text]
        else:
            segment_list = _split_long_text(text, config.max_chunk_chars, config.overlap_chars)

        for segment in segment_list:
            chunk_index += 1
            records.append(
                ChunkRecord(
                    chunk_id=f"{doc_prefix}-{chunk_index:04d}",
                    chunk_index=chunk_index,
                    section_title=section_title,
                    text=segment,
                    text_length=len(segment),
                )
            )

    return records
