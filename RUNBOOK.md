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

Force live crawling with `requests + BeautifulSoup` instead of local repo snapshot:

```bash
python run_pipeline.py --source web
```

Windows quick launchers:
- `crawl_web_learning.bat`: run live web crawl into `data/web_learning`
- `crawl_repo_snapshot.bat`: run local `index_repo` snapshot mode
- `train_web_learning.bat`: build `keyword_index.json` and `learning_profile.json` under `data/web_learning`

Build learning artifacts for a custom data root:

```bash
python train_index_only.py --data-root data/web_learning --skip-pipeline
python train_learning_profile.py --data-root data/web_learning
```

Useful crawl flags:
- `--max-pages 120`
- `--delay 0.5`
- `--timeout 20`
- `--data-root data/web_learning`

Source modes:
- `auto`: prefer local `index_repo/`, fallback to live site crawl
- `repo`: only read local HTML snapshot from `index_repo/`
- `web`: always crawl the live site with `requests + BeautifulSoup`

## Continuous Learning Profile (Core First)

Generate and update persistent learning record:

```bash
python train_learning_profile.py
```

Output file:
- `data/learning_profile.json`

This file stores:
- `core_keywords`: high-priority core topics for retrieval boost
- `secondary_keywords`: secondary topics
- `feedback_terms`: terms mined from positive feedback questions
- `trained_runs`: number of profile retraining runs

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

## Evaluate with Fixed Question Set
Run the benchmark script against a stable question set:

```bash
python tools/evaluate_fixed_set.py
```

Optional flags:
- `--chunk-file data/chunks/chunks.jsonl`
- `--question-set data/eval/fixed_questions.json`
- `--output data/eval/fixed_set_report.json`

Default outputs:
- Console summary with pass/fail per case.
- JSON report at `data/eval/fixed_set_report.json`.

## Start API + Web Chat
```bash
python run_api.py
```

## Optional: local LLM boost (Ollama)

This project can keep BM25 retrieval and optionally let a local LLM rewrite the
final conclusion for better readability.

1. Install Ollama and pull a small model (example):

```bash
ollama pull qwen2.5:3b
```

2. Enable LLM enhancement before starting API:

```bash
set OLLAMA_ENABLED=1
set OLLAMA_MODEL=qwen2.5:3b
set OLLAMA_BASE_URL=http://127.0.0.1:11434
python run_api.py
```

When disabled (default), system behaves exactly like BM25-only mode.

## Optional: cloud LLM boost (OpenAI API)

You can switch to OpenAI-compatible API without changing retrieval logic.

```bash
set LLM_ENABLED=1
set LLM_PROVIDER=openai
set OPENAI_API_KEY=<your_api_key>
set OPENAI_MODEL=gpt-4o-mini
python run_api.py
```

Optional custom endpoint (OpenAI-compatible):

```bash
set OPENAI_BASE_URL=https://api.openai.com/v1
```

Then open:
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/admin`

API endpoints:
- `GET /health`
- `POST /api/ask`
- `POST /api/feedback`
- `GET /api/admin/summary`

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
- `data/eval/fixed_set_report.json`: fixed question set evaluation report

## Admin Dashboard
- Page: `/admin`
- Shows:
  - total ask count
  - total feedback count
  - up/down feedback counts
  - average confidence
  - top asked questions
  - low-confidence questions to prioritize content fixes

## Pipeline Behavior (v1)
- Allowed source starts at: https://taiwangoldfish.github.io/index/
- Source priority:
  - `auto` mode: first local repository folder `index_repo/`, fallback to live website crawl
  - `web` mode: always use live website crawl via `requests + BeautifulSoup`
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
