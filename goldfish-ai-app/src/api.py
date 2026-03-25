from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .qa import QAEngine
from .reporting import generate_daily_report
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


class AdminCase(BaseModel):
    interaction_id: str
    timestamp: str
    question: str
    conclusion: str
    confidence: float
    rating: str
    comment: str
    source_urls: list[str]


class AdminCasesResponse(BaseModel):
    mode: str
    total: int
    items: list[AdminCase]


class DailyReportResponse(BaseModel):
    date: str
    markdown_path: str
    csv_path: str
    total_asks: int
    low_confidence_count: int
    down_feedback_count: int


class DailyReportContentResponse(BaseModel):
    date: str
    content: str


def _read_logs(log_file: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not log_file.exists():
        return [], []

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

    return asks, feedbacks


def _build_admin_cases(
    asks: list[dict[str, object]],
    feedbacks: list[dict[str, object]],
    *,
    mode: str,
    limit: int,
) -> list[AdminCase]:
    feedback_map: dict[str, dict[str, str]] = {}
    for row in feedbacks:
        iid = str(row.get("interaction_id", ""))
        if not iid:
            continue
        feedback_map[iid] = {
            "rating": str(row.get("rating", "")),
            "comment": str(row.get("comment", "")),
        }

    cases: list[AdminCase] = []
    for ask in reversed(asks):
        iid = str(ask.get("interaction_id", ""))
        confidence = float(ask.get("confidence", 0.0) or 0.0)
        fb = feedback_map.get(iid, {"rating": "", "comment": ""})
        rating = fb.get("rating", "")

        if mode == "low" and confidence >= 0.35:
            continue
        if mode == "down" and rating != "down":
            continue

        cases.append(
            AdminCase(
                interaction_id=iid,
                timestamp=str(ask.get("timestamp", "")),
                question=str(ask.get("question", "")),
                conclusion=str(ask.get("conclusion", "")),
                confidence=round(confidence, 3),
                rating=rating,
                comment=fb.get("comment", ""),
                source_urls=[str(x) for x in ask.get("source_urls", [])],
            )
        )

        if len(cases) >= limit:
            break

    return cases


def create_app(chunk_file: Path = Path("data/chunks/chunks.jsonl")) -> FastAPI:
    app = FastAPI(title="Goldfish AI API", version="0.1.0")
    engine = QAEngine.from_chunk_file(chunk_file)

    web_dir = Path(__file__).resolve().parent.parent / "web"
    log_file = Path("data/logs/interactions.jsonl")
    report_dir = Path("data/reports")
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
        asks, feedbacks = _read_logs(log_file)
        if not asks and not feedbacks:
            return AdminSummaryResponse(
                total_asks=0,
                total_feedback=0,
                up_count=0,
                down_count=0,
                avg_confidence=0.0,
                low_confidence_questions=[],
                top_questions=[],
            )

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
    def admin_cases(
        mode: str = Query(default="all", pattern="^(all|low|down)$"),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> AdminCasesResponse:
        asks, feedbacks = _read_logs(log_file)
        items = _build_admin_cases(asks, feedbacks, mode=mode, limit=limit)
        return AdminCasesResponse(mode=mode, total=len(items), items=items)

    @app.get("/api/admin/cases.csv")
    def admin_cases_csv(
        mode: str = Query(default="all", pattern="^(all|low|down)$"),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> Response:
        asks, feedbacks = _read_logs(log_file)
        items = _build_admin_cases(asks, feedbacks, mode=mode, limit=limit)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["interaction_id", "timestamp", "question", "conclusion", "confidence", "rating", "comment", "source_urls"])
        for item in items:
            writer.writerow(
                [
                    item.interaction_id,
                    item.timestamp,
                    item.question,
                    item.conclusion,
                    item.confidence,
                    item.rating,
                    item.comment,
                    " | ".join(item.source_urls),
                ]
            )

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=admin-cases-{mode}.csv"},
        )

    @app.post("/api/admin/report/generate", response_model=DailyReportResponse)
    def generate_report(date: str | None = Query(default=None)) -> DailyReportResponse:
        result = generate_daily_report(log_file, report_dir, target_date=date)
        return DailyReportResponse(
            date=result.date,
            markdown_path=str(result.markdown_path).replace("\\", "/"),
            csv_path=str(result.csv_path).replace("\\", "/"),
            total_asks=result.total_asks,
            low_confidence_count=result.low_confidence_count,
            down_feedback_count=result.down_feedback_count,
        )

    @app.get("/api/admin/report/latest", response_model=DailyReportContentResponse)
    def latest_report() -> DailyReportContentResponse:
        latest = report_dir / "daily-report-latest.md"
        if latest.exists():
            content = latest.read_text(encoding="utf-8")
            date_value = latest.stem.replace("daily-report-latest", "latest")
            return DailyReportContentResponse(date=date_value, content=content)

        result = generate_daily_report(log_file, report_dir)
        content = result.markdown_path.read_text(encoding="utf-8")
        return DailyReportContentResponse(date=result.date, content=content)

    return app


app = create_app()
