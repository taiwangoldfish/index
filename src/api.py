from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import re
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .qa import QAEngine
from .telemetry import append_jsonl


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class SourceModel(BaseModel):
    title: str
    section: str
    url: str


class AskResponse(BaseModel):
    interaction_id: str
    conclusion: str
    confidence: float
    evidence: list[str]
    sources: list[SourceModel]
    matched_keywords: list[str] = []
    matched_keywords_total: int = 0


class FeedbackRequest(BaseModel):
    interaction_id: str = Field(..., min_length=8)
    rating: str = Field(..., pattern="^(up|down)$")
    comment: str = Field(default="", max_length=500)


class FeedbackResponse(BaseModel):
    ok: bool


class AdminSummaryResponse(BaseModel):
    total_asks: int
    total_feedback: int
    up_count: int
    down_count: int
    avg_confidence: float
    low_confidence_questions: list[str]
    top_questions: list[str]


class SuggestedTemplate(BaseModel):
    page_title: str
    page_url: str
    keywords: list[str]
    template: str


class AdminCase(BaseModel):
    interaction_id: str
    timestamp: str
    question: str
    conclusion: str
    confidence: float
    rating: str | None
    comment: str | None
    source_urls: list[str]
    suggested_keywords: list[str]
    suggested_pages: list[str]
    suggested_templates: list[SuggestedTemplate]


class AdminCasesResponse(BaseModel):
    total: int
    cases: list[AdminCase]


@dataclass
class PageMetadata:
    """Page title and URL for mapping"""
    page_url: str
    page_title: str


# Regex patterns for keyword extraction
ZH_BLOCK_RE = re.compile(r'[\u4e00-\u9fff]{2,}')
EN_WORD_RE = re.compile(r'[a-zA-Z]{3,}')


def _extract_keywords(question: str, limit: int = 6) -> list[str]:
    """Extract keywords from question text (both Chinese and English)."""
    keywords = set()
    
    # Extract Chinese phrases (2+ chars)
    for match in ZH_BLOCK_RE.finditer(question):
        keyword = match.group()
        if keyword and len(keyword) <= 20:
            keywords.add(keyword)
    
    # Extract English words (3+ chars)
    for match in EN_WORD_RE.finditer(question):
        keyword = match.group()
        if keyword.lower() not in {'the', 'and', 'for', 'are', 'how', 'why', 'can'}:
            keywords.add(keyword)
    
    keywords_list = sorted(list(keywords))[:limit]
    return keywords_list


def _load_page_metadata() -> dict[str, PageMetadata]:
    """Load page URL to title mapping from documents.jsonl."""
    metadata = {}
    doc_file = Path("data/chunks/documents.jsonl")
    
    if not doc_file.exists():
        return metadata
    
    with doc_file.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                url = doc.get("page_url")
                title = doc.get("page_title", "Page Content")
                if url:
                    metadata[url] = PageMetadata(page_url=url, page_title=title)
            except json.JSONDecodeError:
                continue
    
    return metadata


def _generate_paragraph_template(
    page_title: str, 
    question: str, 
    keywords: list[str]
) -> str:
    """Generate a paragraph supplement template for content editors."""
    if not keywords:
        keywords = ["相關說明"]
    
    template = f"""【補充頁面】{page_title}

用戶提問：「{question}」

建議補充段落：

## 📌 {keywords[0]}
[請這裡添加關於「{keywords[0]}」的詳細說明]

"""
    
    for keyword in keywords[1:]:
        template += f"## 📌 {keyword}\n[請這裡添加關於「{keyword}」的詳細說明]\n\n"
    
    template += """---
**補充提示**：
- 用簡潔的語言解釋，避免過於專業的術語
- 如果可能，配上相關照片或圖表
- 考慮用 Q&A 形式說明
"""
    
    return template


def _build_admin_cases(
    log_file: Path,
    page_metadata: dict[str, PageMetadata]
) -> list[AdminCase]:
    """Build admin case list with suggestions from telemetry logs."""
    if not log_file.exists():
        return []
    
    # Read telemetry logs
    asks: dict[str, dict[str, object]] = {}
    feedbacks: dict[str, dict[str, object]] = {}
    
    with log_file.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            row_type = row.get("type")
            if row_type == "ask":
                interaction_id = row.get("interaction_id")
                if interaction_id:
                    asks[interaction_id] = row
            elif row_type == "feedback":
                interaction_id = row.get("interaction_id")
                if interaction_id:
                    feedbacks[interaction_id] = row
    
    # Track problematic pages (pages in low-confidence or negative feedback cases)
    page_problem_count: dict[str, int] = {}
    
    cases = []
    for interaction_id, ask in asks.items():
        question = str(ask.get("question", "")).strip()
        confidence = float(ask.get("confidence", 0.0) or 0.0)
        timestamp = str(ask.get("timestamp", ""))
        conclusion = str(ask.get("conclusion", ""))
        source_urls = ask.get("source_urls", [])
        if not isinstance(source_urls, list):
            source_urls = []
        
        # Track problematic pages
        is_low_conf = confidence < 0.35
        fb = feedbacks.get(interaction_id, {})
        is_negative = str(fb.get("rating", "")).lower() == "down"
        
        if is_low_conf or is_negative:
            for url in source_urls:
                page_problem_count[url] = page_problem_count.get(url, 0) + 1
        
        # Extract keywords from question
        keywords = _extract_keywords(question)
        
        # Get top 3 problematic pages (fallback to source URLs if available)
        suggested_pages = []
        if source_urls:
            # Use source URLs if available
            suggested_pages = source_urls[:3]
        else:
            # Fallback: use pages with most problems
            sorted_pages = sorted(
                page_problem_count.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            suggested_pages = [url for url, _ in sorted_pages[:3]]
        
        # Generate templates for each suggested page
        templates = []
        for page_url in suggested_pages:
            meta = page_metadata.get(page_url)
            page_title = meta.page_title if meta else "Page Content"
            template_text = _generate_paragraph_template(page_title, question, keywords)
            templates.append(
                SuggestedTemplate(
                    page_title=page_title,
                    page_url=page_url,
                    keywords=keywords,
                    template=template_text
                )
            )
        
        # Get feedback if available
        rating = str(feedbacks.get(interaction_id, {}).get("rating", "")).lower()
        if rating not in {"up", "down"}:
            rating = None
        comment = str(feedbacks.get(interaction_id, {}).get("comment", ""))
        
        case = AdminCase(
            interaction_id=interaction_id,
            timestamp=timestamp,
            question=question,
            conclusion=conclusion,
            confidence=round(confidence, 3),
            rating=rating,
            comment=comment if comment else None,
            source_urls=source_urls,
            suggested_keywords=keywords,
            suggested_pages=suggested_pages,
            suggested_templates=templates,
        )
        
        cases.append(case)
    
    # Sort by timestamp descending
    cases.sort(key=lambda c: c.timestamp, reverse=True)
    
    return cases


def create_app(chunk_file: Path = Path("data/chunks/chunks.jsonl")) -> FastAPI:
    app = FastAPI(title="Goldfish AI API", version="0.1.0")
    engine = QAEngine.from_chunk_file(chunk_file)

    web_dir = Path(__file__).resolve().parent.parent / "web"
    log_file = Path("data/logs/interactions.jsonl")
    app.mount("/web", StaticFiles(directory=web_dir), name="web")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/admin")
    def admin_page() -> FileResponse:
        return FileResponse(web_dir / "admin.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        interaction_id = str(uuid4())
        result = engine.answer_result(req.question, top_k=req.top_k)
        response = result.response
        timestamp = datetime.now(timezone.utc).isoformat()

        append_jsonl(
            log_file,
            {
                "type": "ask",
                "timestamp": timestamp,
                "interaction_id": interaction_id,
                "question": req.question,
                "top_k": req.top_k,
                "confidence": response.confidence,
                "top_score": result.top_score,
                "retrieved_chunk_ids": result.retrieved_chunk_ids,
                "conclusion": response.conclusion,
                "source_urls": [s.url for s in response.sources],
            },
        )

        return AskResponse(
            interaction_id=interaction_id,
            conclusion=response.conclusion,
            confidence=response.confidence,
            evidence=response.evidence,
            sources=[SourceModel(title=s.title, section=s.section, url=s.url) for s in response.sources],
            matched_keywords=getattr(result, "matched_keywords", []),
            matched_keywords_total=len(getattr(result, "matched_keywords", [])),
        )

    @app.post("/api/feedback", response_model=FeedbackResponse)
    def feedback(req: FeedbackRequest) -> FeedbackResponse:
        append_jsonl(
            log_file,
            {
                "type": "feedback",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "interaction_id": req.interaction_id,
                "rating": req.rating,
                "comment": req.comment.strip(),
            },
        )
        return FeedbackResponse(ok=True)

    @app.get("/api/admin/summary", response_model=AdminSummaryResponse)
    def admin_summary() -> AdminSummaryResponse:
        if not log_file.exists():
            return AdminSummaryResponse(
                total_asks=0,
                total_feedback=0,
                up_count=0,
                down_count=0,
                avg_confidence=0.0,
                low_confidence_questions=[],
                top_questions=[],
            )

        asks: list[dict[str, object]] = []
        feedbacks: list[dict[str, object]] = []
        with log_file.open("r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                row_type = row.get("type")
                if row_type == "ask":
                    asks.append(row)
                elif row_type == "feedback":
                    feedbacks.append(row)

        question_counts: dict[str, int] = {}
        low_confidence_questions: list[str] = []
        confidence_sum = 0.0

        for ask in asks:
            question = str(ask.get("question", "")).strip()
            if question:
                question_counts[question] = question_counts.get(question, 0) + 1

            confidence = float(ask.get("confidence", 0.0) or 0.0)
            confidence_sum += confidence
            if confidence < 0.35 and question:
                low_confidence_questions.append(question)

        up_count = 0
        down_count = 0
        for fb in feedbacks:
            rating = str(fb.get("rating", "")).lower()
            if rating == "up":
                up_count += 1
            elif rating == "down":
                down_count += 1

        sorted_questions = sorted(question_counts.items(), key=lambda x: x[1], reverse=True)
        top_questions = [q for q, _ in sorted_questions[:10]]

        avg_confidence = (confidence_sum / len(asks)) if asks else 0.0

        return AdminSummaryResponse(
            total_asks=len(asks),
            total_feedback=len(feedbacks),
            up_count=up_count,
            down_count=down_count,
            avg_confidence=round(avg_confidence, 3),
            low_confidence_questions=low_confidence_questions[:20],
            top_questions=top_questions,
        )

    @app.get("/api/admin/cases", response_model=AdminCasesResponse)
    def admin_cases(mode: str = "all") -> AdminCasesResponse:
        """Get admin cases with suggestions.
        
        mode:
            - "all": All cases
            - "low": Low confidence cases (< 0.35)
            - "down": Cases with negative feedback
        """
        page_metadata = _load_page_metadata()
        cases = _build_admin_cases(log_file, page_metadata)
        
        # Filter by mode
        if mode == "low":
            cases = [c for c in cases if c.confidence < 0.35]
        elif mode == "down":
            cases = [c for c in cases if c.rating == "down"]
        
        return AdminCasesResponse(total=len(cases), cases=cases)

    return app


app = create_app()
