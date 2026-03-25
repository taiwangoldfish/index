# Goldfish AI Runbook

## Purpose
This runbook describes how to run and maintain the first implementation of the data pipeline:
- crawl
- clean
- chunk
- export JSONL artifacts

## Current Entry Point
- Script: `run_pipeline.py`
- QA CLI: `ask.py`
- API server: `run_api.py`

## Environment Setup
1. Activate the local Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run Pipeline
```bash
python run_pipeline.py
```

## Ask Questions (BM25 v1)
```bash
python ask.py "如何翻鰓?"
```

Optional flags:
- `--chunk-file data/chunks/chunks.jsonl`
- `--top-k 5`

Answer output format:
- `結論`
- `依據`
- `來源`

## Start API + Web Chat
```bash
python run_api.py
```

Then open:
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/admin`

API endpoints:
- `GET /health`
- `POST /api/ask`
- `POST /api/feedback`
- `GET /api/admin/summary`
- `GET /api/admin/cases?mode=all|low|down&limit=80`
- `GET /api/admin/cases.csv?mode=all|low|down&limit=200`

Example request body:
```json
{
  "question": "如何翻鰓?",
  "top_k": 5
}
```

Example feedback body:
```json
{
  "interaction_id": "<ask-response-id>",
  "rating": "up",
  "comment": "很清楚"
}
```

## Output Artifacts
- `data/raw/`: raw HTML snapshots
- `data/clean/`: cleaned markdown-like text files
- `data/chunks/chunks.jsonl`: chunk-level records
- `data/chunks/documents.jsonl`: document-level records
- `data/ocr/image_ocr.jsonl`: image OCR records
- `data/logs/interactions.jsonl`: ask + feedback telemetry logs

## Admin Dashboard
- Page: `/admin`
- Shows:
  - total ask count
  - total feedback count
  - up/down feedback counts
  - average confidence
  - top asked questions
  - low-confidence questions to prioritize content fixes
  - latest cases table with filter modes:
    - `all`: all recent asks
    - `low`: confidence < 0.35
    - `down`: feedback = down
  - CSV export for case review outside the UI

## Pipeline Behavior (v1)
- Allowed source starts at: https://taiwangoldfish.github.io/index/
- Source priority:
  - First: local repository folder index_repo (if exists)
  - Fallback: live website crawl
- Utility pages included:
  - https://taiwangoldfish.github.io/MLE/
  - https://taiwangoldfish.github.io/fish-tank-circulation/
- Excludes external domains and static assets.
- Image handling:
  - Parse `<img>` references from each HTML page.
  - Resolve local repo images and GitHub raw image links into local files when possible.
  - Extract OCR text and append it to `chunks.jsonl` as `source_type=image_ocr`.

## Known Limitations (v1)
- HTML structure rules are generic; some sections may still include minor UI noise.
- OCR quality depends on image clarity and language packs.
- If Tesseract binary is missing, OCR may produce fewer image chunks.
- Retrieval is BM25-only right now (no dense vector search yet).
- Web UI is local-only static chat page (no auth / no rate limit).
- Confidence is BM25-derived heuristic, not a calibrated probability.

## Next Development Steps
1. Build vector index from `chunks.jsonl`.
2. Add hybrid retrieval (dense + sparse).
3. Add answer generation with strict citation format.
4. Add evaluation script with fixed question set.

## Change Discipline
- Update this runbook when command, output path, or pipeline behavior changes.
- Keep `DEVELOPMENT_PLAN.md` and code behavior aligned.
