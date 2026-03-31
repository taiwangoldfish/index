from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.qa import NOT_FOUND_TEXT, QAEngine  # noqa: E402


@dataclass
class EvalCase:
    case_id: str
    question: str
    expected_url_fragments: list[str]
    expected_terms: list[str]
    min_term_hits: int
    min_confidence: float | None
    max_confidence: float | None
    expect_not_found: bool
    top_k: int


@dataclass
class EvalCaseResult:
    case_id: str
    question: str
    passed: bool
    checks: dict[str, bool]
    confidence: float
    conclusion: str
    source_urls: list[str]
    matched_expected_fragments: list[str]
    matched_expected_terms: list[str]


def _load_cases(path: Path) -> list[EvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Question set must be a JSON array")

    cases: list[EvalCase] = []
    for idx, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Case #{idx} must be an object")

        case_id = str(row.get("id", f"case-{idx:02d}")).strip() or f"case-{idx:02d}"
        question = str(row.get("question", "")).strip()
        if not question:
            raise ValueError(f"Case {case_id} is missing question")

        expected_url_fragments = [str(x).strip() for x in row.get("expected_url_fragments", []) if str(x).strip()]
        expected_terms = [str(x).strip() for x in row.get("expected_terms", []) if str(x).strip()]

        min_term_hits = int(row.get("min_term_hits", 1))
        min_confidence = row.get("min_confidence")
        max_confidence = row.get("max_confidence")

        cases.append(
            EvalCase(
                case_id=case_id,
                question=question,
                expected_url_fragments=expected_url_fragments,
                expected_terms=expected_terms,
                min_term_hits=max(0, min_term_hits),
                min_confidence=float(min_confidence) if min_confidence is not None else None,
                max_confidence=float(max_confidence) if max_confidence is not None else None,
                expect_not_found=bool(row.get("expect_not_found", False)),
                top_k=int(row.get("top_k", 5)),
            )
        )
    return cases


def _evaluate_case(engine: QAEngine, case: EvalCase) -> EvalCaseResult:
    qa_result = engine.answer_result(case.question, top_k=case.top_k)
    response = qa_result.response

    source_urls = [src.url for src in response.sources]
    combined_text = "\n".join([response.conclusion, *response.evidence]).lower()

    matched_fragments: list[str] = []
    for fragment in case.expected_url_fragments:
        f = fragment.lower()
        if any(f in url.lower() for url in source_urls):
            matched_fragments.append(fragment)

    matched_terms: list[str] = []
    for term in case.expected_terms:
        if term.lower() in combined_text:
            matched_terms.append(term)

    checks: dict[str, bool] = {}
    checks["sources_present"] = bool(source_urls) if not case.expect_not_found else True
    checks["fragment_match"] = True
    if case.expected_url_fragments:
        checks["fragment_match"] = len(matched_fragments) > 0

    checks["term_match"] = True
    if case.expected_terms:
        checks["term_match"] = len(matched_terms) >= case.min_term_hits

    checks["min_confidence"] = True
    if case.min_confidence is not None:
        checks["min_confidence"] = response.confidence >= case.min_confidence

    checks["max_confidence"] = True
    if case.max_confidence is not None:
        checks["max_confidence"] = response.confidence <= case.max_confidence

    checks["not_found_behavior"] = True
    if case.expect_not_found:
        checks["not_found_behavior"] = (
            NOT_FOUND_TEXT in response.conclusion
            or (response.confidence <= (case.max_confidence if case.max_confidence is not None else 0.25))
        )

    passed = all(checks.values())
    return EvalCaseResult(
        case_id=case.case_id,
        question=case.question,
        passed=passed,
        checks=checks,
        confidence=response.confidence,
        conclusion=response.conclusion,
        source_urls=source_urls,
        matched_expected_fragments=matched_fragments,
        matched_expected_terms=matched_terms,
    )


def _build_summary(results: list[EvalCaseResult], cases: list[EvalCase]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    answerable_total = sum(1 for c in cases if not c.expect_not_found)
    answerable_pass = sum(1 for r, c in zip(results, cases) if not c.expect_not_found and r.passed)

    citation_expected_total = sum(1 for c in cases if c.expected_url_fragments)
    citation_hit_total = sum(1 for r, c in zip(results, cases) if c.expected_url_fragments and len(r.matched_expected_fragments) > 0)

    term_expected_total = sum(1 for c in cases if c.expected_terms)
    term_hit_total = sum(1 for r, c in zip(results, cases) if c.expected_terms and len(r.matched_expected_terms) >= c.min_term_hits)

    avg_conf = sum(r.confidence for r in results) / total if total else 0.0

    return {
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": round((passed / total) if total else 0.0, 4),
        "answerable_pass_rate": round((answerable_pass / answerable_total) if answerable_total else 0.0, 4),
        "citation_hit_rate": round((citation_hit_total / citation_expected_total) if citation_expected_total else 0.0, 4),
        "term_hit_rate": round((term_hit_total / term_expected_total) if term_expected_total else 0.0, 4),
        "avg_confidence": round(avg_conf, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate QA quality with a fixed question set")
    parser.add_argument(
        "--chunk-file",
        type=Path,
        default=Path("data/chunks/chunks.jsonl"),
        help="Path to chunk JSONL file",
    )
    parser.add_argument(
        "--question-set",
        type=Path,
        default=Path("data/eval/fixed_questions.json"),
        help="Path to evaluation question set",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/eval/fixed_set_report.json"),
        help="Path to write evaluation report JSON",
    )
    args = parser.parse_args()

    if not args.chunk_file.exists():
        raise FileNotFoundError(f"Chunk file not found: {args.chunk_file}")
    if not args.question_set.exists():
        raise FileNotFoundError(f"Question set not found: {args.question_set}")

    cases = _load_cases(args.question_set)
    engine = QAEngine.from_chunk_file(args.chunk_file)
    results = [_evaluate_case(engine, case) for case in cases]

    summary = _build_summary(results, cases)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chunk_file": str(args.chunk_file),
        "question_set": str(args.question_set),
        "summary": summary,
        "cases": [
            {
                "id": r.case_id,
                "question": r.question,
                "passed": r.passed,
                "confidence": round(r.confidence, 4),
                "checks": r.checks,
                "matched_expected_fragments": r.matched_expected_fragments,
                "matched_expected_terms": r.matched_expected_terms,
                "source_urls": r.source_urls,
                "conclusion": r.conclusion,
            }
            for r in results
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"report={args.output}")
    print(
        "summary="
        + json.dumps(summary, ensure_ascii=False)
    )
    for r in results:
        print(
            f"{r.case_id} passed={r.passed} conf={r.confidence:.2f} "
            f"fragment_hits={len(r.matched_expected_fragments)} term_hits={len(r.matched_expected_terms)}"
        )


if __name__ == "__main__":
    main()
