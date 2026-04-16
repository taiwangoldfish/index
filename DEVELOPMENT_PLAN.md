# Goldfish AI Development Plan

## 1) Project Goal
- Build a goldfish Q&A assistant whose answers come from this source only:
	- https://taiwangoldfish.github.io/index/
- Prioritize accuracy, traceability, and low hallucination.
- Default reply language: Traditional Chinese.
- Organic growth goal: become the leading Traditional Chinese goldfish learning website for beginners and hobbyists, so users can quickly learn correct methods and avoid common mistakes.

## 2) Scope Rules
- In scope:
	- Crawl and parse pages under the target site with explicit allowlist rules.
	- Build a searchable knowledge base.
	- Use retrieval-augmented generation (RAG) for answering.
	- Show answer with source evidence.
- Out of scope (for now):
	- Multi-site ingestion.
	- Model fine-tuning from day one.
	- Complex UI polish before core quality is validated.

## 3) Development Strategy (Agreed)
### Phase A: RAG First (MVP)
- Why:
	- Fastest path to a useful system.
	- Content updates can be reflected by re-indexing, no retraining needed.
- Deliverables:
	- Data pipeline (crawl -> clean -> chunk -> index).
	- Q&A pipeline (retrieve -> answer -> cite source).
	- Basic chat UI (desktop + mobile compatible).
	- Evaluation set (10-20 questions) and quality checks.

### Phase B: Training Later (After Data)
- Start only when enough usage data exists:
	- Real user questions.
	- Accepted/rejected answers.
	- Corrected reference answers.
- Candidate methods:
	- Supervised fine-tuning (SFT) for style/format consistency.
	- Preference optimization for better ranking of responses.
- Keep RAG even after training for grounding and freshness.

## 4) Answer Policy
- Every answer should include:
	- Direct conclusion.
	- Evidence summary from retrieved content.
	- Source reference (page title or path).
- If evidence is weak or missing:
	- Reply that information is not found in current source data.
	- Do not invent facts.

## 5) Data Pipeline Spec
### 5.1 Crawl
- Start URL:
	- https://taiwangoldfish.github.io/index/
- Source priority (implemented):
	- First: ingest HTML files from GitHub repository snapshot (`index_repo/`).
	- Fallback: crawl live website when local repository snapshot is unavailable.
- Allowed URLs (v1):
	- https://taiwangoldfish.github.io/index/
	- Internal same-domain pages linked from the start page that contain knowledge content.
	- Utility pages that are part of this site knowledge flow, including:
		- https://taiwangoldfish.github.io/MLE/
		- https://taiwangoldfish.github.io/fish-tank-circulation/
- Excluded URLs (v1):
	- External domains (for example line.me, hitwebcounter, raw.githubusercontent assets).
	- Fragment-only duplicates that point to the same page section repeatedly.
	- Static assets (images, css, js) as answer sources.
- Crawl behavior:
	- Normalize URLs and de-duplicate before fetch.
	- Respect robots and polite rate limits.
	- Save source URL and crawl timestamp for every document.
	- Parse image references in HTML and include OCR-extracted text as supplementary chunks.
- Store raw HTML snapshots for reproducibility.

### 5.2 Clean
- Parsing and normalization rules:
	- Parse with a robust HTML parser and extract visible text only.
	- Drop script/style/noscript/iframe blocks.
	- Normalize whitespace, line breaks, and punctuation spacing.
	- Preserve Traditional Chinese content as-is (no automatic language conversion).
- Content selection rules:
	- Keep semantic text blocks: headings, paragraphs, list items, table text.
	- Remove UI noise: nav labels, repeated menu entries, footer boilerplate, counters.
	- Remove social/join links and unrelated promo blocks from answer corpus.
	- Keep section order exactly as presented on page.
- De-duplication rules:
	- Remove exact duplicate lines after normalization.
	- Remove near-duplicate consecutive blocks that only differ by decorative symbols.
	- Keep one canonical copy and attach source metadata.
- Output requirement:
	- Store one cleaned markdown-like text file per crawled page.
	- Keep content in UTF-8.

### 5.3 Chunk
- Chunking strategy:
	- Primary split by heading hierarchy (H1/H2/H3 equivalent).
	- Secondary split by paragraph groups when sections are too long.
	- Keep heading text inside each chunk for context anchoring.
- Size and overlap (v1 defaults):
	- Target chunk length: 500-900 Chinese characters.
	- Hard max length: 1200 Chinese characters.
	- Overlap: 80-150 Chinese characters between adjacent chunks.
- Special handling:
	- Lists and tables stay with their nearest heading.
	- Do not split short Q&A pairs across different chunks.
	- Utility/calculator pages should be chunked as instructions + formula notes.
- Required metadata per chunk:
	- chunk_id
	- page_url
	- page_title
	- section_title
	- chunk_index
	- crawl_timestamp
	- text_length

### 5.4 Index
- Index architecture (v1):
	- Primary: dense vector index for semantic retrieval.
	- Secondary: BM25/keyword index for lexical fallback.
	- Optional: hybrid score = alpha * dense + (1 - alpha) * sparse.
- Recommended defaults (v1):
	- Embedding dimension: model default.
	- Similarity metric: cosine similarity.
	- Top-K dense retrieval: 8.
	- Top-K sparse retrieval: 8.
	- Hybrid alpha: 0.7 (dense priority).
	- Final context chunks to LLM: 4-6.
- Re-ranking (v1):
	- Use lightweight cross-encoder or LLM rerank prompt.
	- Keep top 4-6 chunks by rerank score.
	- Enforce source diversity when possible (avoid all chunks from same tiny section).
- Index update policy:
	- Full rebuild for first release.
	- Incremental update by changed page hash in later versions.
	- Keep index version id and build timestamp.

### 5.5 Normalized Data Format
- Document-level JSON example:

```json
{
  "doc_id": "sha1_of_url_or_content",
  "page_url": "https://taiwangoldfish.github.io/index/",
  "page_title": "金魚養殖經驗教學群",
  "crawl_timestamp": "2026-03-25T10:30:00Z",
  "clean_text_path": "data/clean/index.md",
  "chunks": [
    {
      "chunk_id": "index-0001",
      "chunk_index": 1,
      "section_title": "金魚基本飼養方式及配備",
      "text": "...",
      "text_length": 736
    }
  ]
}
```

- Storage suggestion (v1):
	- `data/raw/` for raw HTML snapshots.
	- `data/clean/` for cleaned text.
	- `data/chunks/` for chunk JSONL.
	- `data/ocr/` for image OCR JSONL.
	- `data/index/` for vector index artifacts.

## 6) Q&A Pipeline Spec
### 6.1 Runtime Steps
1. Receive user question.
2. Run dense + sparse retrieval.
3. Merge and rerank results.
4. Run evidence sufficiency check.
5. Generate response using only retrieved context.
6. Return answer + citations + confidence signal.

### 6.2 Evidence Sufficiency Check
- If no chunk passes minimum relevance threshold:
	- Return: "目前資料中找不到足夠資訊回答此問題。"
- If chunks are partially relevant only:
	- Return a partial answer and explicitly mark uncertainty.
- Default thresholds (v1):
	- minimum dense similarity: 0.35
	- minimum rerank score: implementation-defined percentile (top 40% kept)

### 6.3 Generation Constraints
- System constraint:
	- Answer only from provided context chunks.
	- Do not use external facts.
	- If context is insufficient, say not found.
- Output format (strict):
	- `結論`: 1-3 sentences.
	- `依據`: 1-3 bullet points from retrieved evidence.
	- `來源`: page title + URL/path for each cited chunk.

### 6.4 Citation Format (v1)
- Citation item example:
	- `[來源 1] 金魚養殖經驗教學群 / 金魚基本飼養方式及配備`
	- `URL: https://taiwangoldfish.github.io/index/`
- Rule:
	- At least 1 citation required for every non-empty answer.
	- If claim count > 3, target at least 2 citations.

### 6.5 Fallback and Safety Behavior
- Retrieval failure:
	- Return not-found template and suggest a narrower question.
- Ambiguous question:
	- Ask one concise clarification question before answering.
- Conflicting evidence across chunks:
	- Present both and mark conflict clearly.

### 6.6 Telemetry (for future training)
- Log per request:
	- question
	- retrieved chunk ids
	- final citations
	- answer text
	- user feedback (thumb up/down)
	- latency
- Purpose:
	- Build future fine-tuning and evaluation dataset.

Implementation status:
	- `POST /api/ask` now writes interaction logs with `interaction_id`.
	- `POST /api/feedback` writes thumbs up/down linked by `interaction_id`.
	- Logs are stored in `data/logs/interactions.jsonl`.

## 7) Quality Gates
- Gate 1: Source grounding
	- No citation -> fail.
- Gate 2: Hallucination control
	- Claims not in source -> fail.
- Gate 3: Coverage
	- At least one relevant evidence chunk for answerable questions.
- Gate 4: UX baseline
	- Mobile chat usable.
	- Source section visible.

## 8) Evaluation Plan
- Build a benchmark set:
	- 10-20 representative goldfish questions.
	- Include easy, medium, and edge cases.
- For each answer, score:
	- correctness
	- citation quality
	- completeness
	- hallucination risk

## 9) Documentation Rules (Must Follow)
- Update docs with every meaningful change.
- Keep decision log for architecture choices.
- Record known limitations and next actions.
- Write short runbook steps for setup and execution.

## 10) Immediate Next Steps
1. Implement crawler using the v1 allow/exclude rules above.
2. Implement content cleaner with section-level extraction.
3. Build first index from scraped content.
4. Implement Q&A chain with mandatory citations.
5. Create initial evaluation question set.

## 11) Training Readiness Checklist (Future)
- Enough conversation logs collected.
- Data is cleaned and labeled.
- Baseline RAG metrics are stable.
- Clear objective for training (style, ranking, or domain adaptation).
- Regression test suite prepared before any fine-tuning.
