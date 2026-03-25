from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .config import PipelineConfig


@dataclass
class OCRExtractionResult:
    rows: list[dict[str, object]]
    images_seen: int
    images_ocr_success: int


def _to_posix_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def _resolve_local_image_path(html_path: Path, source_repo_dir: Path | None, src: str) -> Path | None:
    parsed = urlparse(src)
    repo_root = source_repo_dir.resolve() if source_repo_dir else None

    if parsed.scheme in {"http", "https"}:
        # Map raw GitHub URL into local repository image path.
        if parsed.netloc.lower() == "raw.githubusercontent.com":
            raw_path = parsed.path.strip("/")
            marker = "/main/"
            if marker in raw_path and repo_root:
                suffix = raw_path.split(marker, 1)[1]
                candidate = repo_root / suffix
                if candidate.exists() and candidate.is_file():
                    return candidate
        return None

    candidate = src.split("?", 1)[0].split("#", 1)[0].strip()
    if not candidate:
        return None

    if repo_root and candidate.startswith("/"):
        path = (repo_root / candidate.lstrip("/")).resolve()
    else:
        # Try page-relative path first, then repo-root path for templates like "image/x.jpg".
        page_relative = (html_path.parent / candidate).resolve()
        repo_relative = (repo_root / candidate).resolve() if repo_root else None
        if page_relative.exists() and page_relative.is_file():
            path = page_relative
        elif repo_relative and repo_relative.exists() and repo_relative.is_file():
            path = repo_relative
        else:
            path = page_relative

    if repo_root:
        try:
            path.relative_to(repo_root)
        except ValueError:
            return None

    if not path.exists() or not path.is_file():
        return None

    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}:
        return None

    return path


def _run_tesseract_ocr(image_path: Path, config: PipelineConfig) -> str:
    image_module = importlib.import_module("PIL.Image")
    pytesseract = importlib.import_module("pytesseract")

    if config.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd

    with image_module.open(image_path) as image:
        text = pytesseract.image_to_string(image, lang=config.ocr_languages)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_image_ocr_rows(
    *,
    html_text: str,
    html_path: Path,
    page_url: str,
    page_title: str,
    doc_id: str,
    config: PipelineConfig,
    processed_images: set[str],
) -> OCRExtractionResult:
    if not config.enable_image_ocr:
        return OCRExtractionResult(rows=[], images_seen=0, images_ocr_success=0)

    soup = BeautifulSoup(html_text, "lxml")
    ocr_rows: list[dict[str, object]] = []
    images_seen = 0
    images_ocr_success = 0

    for image_tag in soup.find_all("img", src=True):
        if len(processed_images) >= config.max_images_per_run:
            break

        src = image_tag.get("src", "").strip()
        if not src:
            continue

        local_image_path = _resolve_local_image_path(html_path, config.source_repo_dir, src)
        if not local_image_path:
            continue

        canonical_path = _to_posix_path(local_image_path)
        if canonical_path in processed_images:
            continue
        processed_images.add(canonical_path)
        images_seen += 1

        alt_text = (image_tag.get("alt") or "").strip()
        ocr_text = ""
        try:
            ocr_text = _run_tesseract_ocr(local_image_path, config)
        except Exception:
            ocr_text = ""

        final_text = ocr_text.strip()
        if not final_text and alt_text:
            final_text = alt_text
        if not final_text:
            final_text = local_image_path.stem.replace("_", " ").strip()

        if len(final_text) < config.ocr_min_text_chars:
            continue

        images_ocr_success += 1
        image_id = hashlib.sha1(canonical_path.encode("utf-8")).hexdigest()[:12]
        row = {
            "doc_id": doc_id,
            "page_url": page_url,
            "page_title": page_title,
            "section_title": "Image OCR",
            "chunk_id": f"{doc_id[:8]}-img-{image_id}",
            "chunk_index": -1,
            "text": final_text,
            "text_length": len(final_text),
            "image_path": canonical_path,
            "image_src": src,
            "source_type": "image_ocr",
        }
        ocr_rows.append(row)

    return OCRExtractionResult(
        rows=ocr_rows,
        images_seen=images_seen,
        images_ocr_success=images_ocr_success,
    )


def write_ocr_jsonl(ocr_dir: Path, rows: list[dict[str, object]]) -> Path:
    ocr_dir.mkdir(parents=True, exist_ok=True)
    output_path = ocr_dir / "image_ocr.jsonl"
    with output_path.open("w", encoding="utf-8") as writer:
        for row in rows:
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
    return output_path
