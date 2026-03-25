#!/usr/bin/env python
"""Run the full pipeline and extract top keywords."""
import json
from collections import Counter
from pathlib import Path
import re

from src.config import PipelineConfig
from src.pipeline import run_pipeline

# Run the pipeline
print("🚀 Starting pipeline: crawling → cleaning → chunking → OCR...")
config = PipelineConfig()
summary = run_pipeline(config)

print("\n📊 Pipeline Summary:")
print(f"  Pages crawled: {summary.get('pages_crawled', 0)}")
print(f"  Pages cleaned: {summary.get('pages_cleaned', 0)}")
print(f"  Chunks created: {summary.get('total_chunks', 0)}")
print(f"  Images OCR'd: {summary.get('images_with_ocr', 0)}")

# Extract keywords from chunks
print("\n🔑 Extracting keywords from all chunks...")
chunks_file = config.chunks_dir / "chunks.jsonl"
if not chunks_file.exists():
    print("❌ No chunks file found!")
    exit(1)

# Chinese phrase regex (2+ consecutive Chinese characters)
ZH_PHRASE_RE = re.compile(r'[\u4e00-\u9fff]{2,}')
# English word regex (3+ letters)
EN_WORD_RE = re.compile(r'[a-zA-Z]{3,}')

# Track keyword frequency
keyword_count = Counter()
chunk_keywords = {}  # Map chunk_id to keywords

with chunks_file.open('r', encoding='utf-8') as f:
    for line in f:
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        text = chunk.get('text', '')
        chunk_id = chunk.get('chunk_id', '')
        
        # Extract Chinese phrases
        for match in ZH_PHRASE_RE.finditer(text):
            phrase = match.group()
            if len(phrase) <= 20:  # Reasonable phrase length
                keyword_count[phrase] += 1
        
        # Extract English words
        for match in EN_WORD_RE.finditer(text):
            word = match.group()
            if word.lower() not in {'the', 'and', 'for', 'are', 'that', 'with', 'from', 'have', 'this', 'fish'}:
                keyword_count[word] += 1

print(f"✅ Extracted {len(keyword_count)} unique keywords from {len(chunk_keywords)} chunks")

# Show top 50 keywords
print("\n🏆 Top 50 Keywords:")
print("-" * 60)
print(f"{'Rank':<6} {'Keyword':<25} {'Frequency':<10} {'Domain'}")
print("-" * 60)

for rank, (keyword, freq) in enumerate(keyword_count.most_common(50), 1):
    # Detect if Chinese or English
    domain = "🇹🇼 Chinese" if any('\u4e00' <= c <= '\u9fff' for c in keyword) else "🇬🇧 English"
    print(f"{rank:<6} {keyword:<25} {freq:<10} {domain}")

# Save keyword index to file for training use
keyword_index = dict(keyword_count.most_common(500))
index_file = Path("data/keyword_index.json")
index_file.parent.mkdir(parents=True, exist_ok=True)
with index_file.open('w', encoding='utf-8') as f:
    json.dump(keyword_index, f, ensure_ascii=False, indent=2)

print(f"\n💾 Saved top 500 keywords to data/keyword_index.json")
