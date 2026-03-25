from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .chunker import chunk_sections
from .cleaner import clean_html_to_sections, write_clean_text
from .config import PipelineConfig
from .crawler import crawl_site
from .image_ocr import extract_image_ocr_rows, write_ocr_jsonl
from .repo_source import load_repo_pages


def _doc_id_from_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def run_pipeline(config: PipelineConfig) -> dict[str, int]:
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    config.clean_dir.mkdir(parents=True, exist_ok=True)
    config.chunks_dir.mkdir(parents=True, exist_ok=True)
    config.ocr_dir.mkdir(parents=True, exist_ok=True)

    repo_pages = load_repo_pages(config)
    crawled_pages = repo_pages if repo_pages else crawl_site(config)

    chunk_jsonl_path = config.chunks_dir / "chunks.jsonl"
    docs_jsonl_path = config.chunks_dir / "documents.jsonl"

    total_chunks = 0
    total_docs = 0
    total_images_seen = 0
    total_images_ocr_success = 0
    ocr_rows_all: list[dict[str, object]] = []
    processed_images: set[str] = set()

    with chunk_jsonl_path.open("w", encoding="utf-8") as chunk_writer, docs_jsonl_path.open(
        "w", encoding="utf-8"
    ) as doc_writer:
        for page in crawled_pages:
            html_text = page.html_path.read_text(encoding="utf-8", errors="ignore")
            page_title, sections = clean_html_to_sections(html_text)
            if not sections:
                continue
            if page_title == "Untitled" and sections:
                page_title = sections[0][0]

            clean_text_path = write_clean_text(config.clean_dir, page.url, page_title, sections)

            doc_id = _doc_id_from_url(page.url)
            chunk_records = chunk_sections(doc_id[:8], sections, config)

            ocr_result = extract_image_ocr_rows(
                html_text=html_text,
                html_path=page.html_path,
                page_url=page.url,
                page_title=page_title,
                doc_id=doc_id,
                config=config,
                processed_images=processed_images,
            )
            total_images_seen += ocr_result.images_seen
            total_images_ocr_success += ocr_result.images_ocr_success
            ocr_rows_all.extend(ocr_result.rows)

            crawl_timestamp = datetime.now(timezone.utc).isoformat()
            for record in chunk_records:
                row = {
                    "doc_id": doc_id,
                    "page_url": page.url,
                    "page_title": page_title,
                    "section_title": record.section_title,
                    "chunk_id": record.chunk_id,
                    "chunk_index": record.chunk_index,
                    "text": record.text,
                    "text_length": record.text_length,
                    "crawl_timestamp": crawl_timestamp,
                }
                chunk_writer.write(json.dumps(row, ensure_ascii=False) + "\n")

            for row in ocr_result.rows:
                row["crawl_timestamp"] = crawl_timestamp
                chunk_writer.write(json.dumps(row, ensure_ascii=False) + "\n")

            doc_row = {
                "doc_id": doc_id,
                "page_url": page.url,
                "page_title": page_title,
                "crawl_timestamp": crawl_timestamp,
                "clean_text_path": str(clean_text_path).replace("\\", "/"),
                "chunk_count": len(chunk_records) + len(ocr_result.rows),
                "image_ocr_count": len(ocr_result.rows),
            }
            doc_writer.write(json.dumps(doc_row, ensure_ascii=False) + "\n")

            total_chunks += len(chunk_records) + len(ocr_result.rows)
            total_docs += 1

    ocr_jsonl_path = write_ocr_jsonl(config.ocr_dir, ocr_rows_all)

    return {
        "source_mode": "repo" if repo_pages else "web",
        "crawled_pages": len(crawled_pages),
        "documents_written": total_docs,
        "chunks_written": total_chunks,
        "images_seen": total_images_seen,
        "images_ocr_success": total_images_ocr_success,
        "chunk_file": str(chunk_jsonl_path),
        "doc_file": str(docs_jsonl_path),
        "ocr_file": str(ocr_jsonl_path),
    }
