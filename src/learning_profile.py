from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ZH_BLOCK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")


def _extract_question_terms(text: str) -> list[str]:
    return [m.group() for m in ZH_BLOCK_RE.finditer(text)]


def _load_keyword_index(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    out: dict[str, int] = {}
    for k, v in data.items():
        key = str(k).strip()
        if not key:
            continue
        try:
            out[key] = int(v)
        except Exception:
            continue
    return out


def _load_feedback_terms(path: Path) -> tuple[Counter[str], Counter[str]]:
    if not path.exists():
        return Counter(), Counter()

    asks: dict[str, str] = {}
    feedback_up: set[str] = set()
    feedback_down: set[str] = set()
    up_counter: Counter[str] = Counter()
    down_counter: Counter[str] = Counter()

    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            row_type = str(row.get("type", ""))
            iid = str(row.get("interaction_id", ""))
            if not iid:
                continue

            if row_type == "ask":
                asks[iid] = str(row.get("question", ""))
            elif row_type == "feedback" and str(row.get("rating", "")).lower() == "up":
                feedback_up.add(iid)
            elif row_type == "feedback" and str(row.get("rating", "")).lower() == "down":
                feedback_down.add(iid)

    for iid in feedback_up:
        q = asks.get(iid, "")
        for term in _extract_question_terms(q):
            if len(term) <= 10:
                up_counter[term] += 1

    for iid in feedback_down:
        q = asks.get(iid, "")
        for term in _extract_question_terms(q):
            if len(term) <= 10:
                down_counter[term] += 1

    return up_counter, down_counter


def build_learning_profile(
    keyword_index_path: Path,
    interactions_path: Path,
    output_path: Path,
    core_size: int = 40,
    secondary_size: int = 260,
) -> dict[str, object]:
    keyword_index = _load_keyword_index(keyword_index_path)
    up_terms, down_terms = _load_feedback_terms(interactions_path)

    # Combine static keyword frequency + successful feedback terms.
    merged: Counter[str] = Counter(keyword_index)
    for key, value in up_terms.items():
        merged[key] += value * 10
    for key, value in down_terms.items():
        merged[key] -= value * 6

    stop_words = {
        "小影片",
        "影片",
        "注意事項",
        "為什麼",
        "方式",
        "建議",
        "介紹",
        "分享",
        "圖示",
    }

    ranked: list[tuple[str, int]] = []
    for k, v in merged.items():
        kw = str(k).strip()
        if len(kw) < 2 or kw in stop_words:
            continue
        if v <= 0:
            continue
        ranked.append((kw, int(v)))
    ranked.sort(key=lambda x: (x[1], len(x[0])), reverse=True)

    core_keywords = [k for k, _ in ranked[:core_size]]
    secondary_keywords = [k for k, _ in ranked[core_size : core_size + secondary_size]]

    profile: dict[str, object] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "core_keywords": core_keywords,
        "secondary_keywords": secondary_keywords,
        "feedback_terms_up": dict(up_terms.most_common(80)),
        "feedback_terms_down": dict(down_terms.most_common(80)),
        "stats": {
            "up_term_count": sum(up_terms.values()),
            "down_term_count": sum(down_terms.values()),
            "keyword_index_size": len(keyword_index),
        },
        "trained_runs": 1,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        try:
            old = json.loads(output_path.read_text(encoding="utf-8"))
            profile["trained_runs"] = int(old.get("trained_runs", 0)) + 1
        except Exception:
            pass

    output_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def load_learning_profile(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data
