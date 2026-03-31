from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class PipelineConfig:
    source_mode: str = "auto"
    start_url: str = "https://taiwangoldfish.github.io/index/"
    utility_urls: list[str] = field(
        default_factory=lambda: [
            "https://taiwangoldfish.github.io/MLE/",
            "https://taiwangoldfish.github.io/fish-tank-circulation/",
        ]
    )
    allowed_domain: str = "taiwangoldfish.github.io"
    excluded_domains: set[str] = field(
        default_factory=lambda: {
            "line.me",
            "www.hitwebcounter.com",
            "raw.githubusercontent.com",
        }
    )
    excluded_extensions: set[str] = field(
        default_factory=lambda: {
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
    )
    request_timeout_seconds: int = 20
    crawl_delay_seconds: float = 0.3
    max_pages: int = 300
    user_agent: str = "GoldfishAI/1.0 (+https://taiwangoldfish.github.io/index/)"
    source_repo_dir: Optional[Path] = PROJECT_ROOT / "index_repo"
    enable_image_ocr: bool = True
    max_images_per_run: int = 500
    ocr_min_text_chars: int = 6
    ocr_languages: str = "chi_tra+eng"
    tesseract_cmd: Optional[str] = None

    min_chunk_chars: int = 500
    target_chunk_chars: int = 900
    max_chunk_chars: int = 1200
    overlap_chars: int = 120

    data_root: Path = Path("data")

    @property
    def raw_dir(self) -> Path:
        return self.data_root / "raw"

    @property
    def clean_dir(self) -> Path:
        return self.data_root / "clean"

    @property
    def chunks_dir(self) -> Path:
        return self.data_root / "chunks"

    @property
    def ocr_dir(self) -> Path:
        return self.data_root / "ocr"
