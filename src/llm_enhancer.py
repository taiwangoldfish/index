from __future__ import annotations

import os
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .retriever import RetrievedItem


def is_enabled() -> bool:
    if os.getenv("LLM_ENABLED", "0") == "1":
        return True
    return os.getenv("OLLAMA_ENABLED", "0") == "1"


def _build_prompt(question: str, hits: list["RetrievedItem"]) -> str:
    context_blocks: list[str] = []
    for i, hit in enumerate(hits[:3], start=1):
        text = " ".join(hit.item.text.split())
        context_blocks.append(f"[{i}] {text[:420]}")

    return "\n".join(
        [
            "你是金魚飼養問答助手。只能根據提供的資料片段回答，不可編造。",
            "請用繁體中文，給 1 到 2 句重點結論。",
            f"使用者問題：{question}",
            "資料片段：",
            *context_blocks,
            "請輸出：直接結論，不要加標題。",
        ]
    )


def _enhance_with_ollama(prompt: str, timeout_seconds: float) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

    response = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 180},
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("response", "")).strip()


def _enhance_with_openai(prompt: str, timeout_seconds: float) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.2,
            "max_tokens": 220,
            "messages": [
                {"role": "system", "content": "你是金魚飼養問答助手。只能根據資料回答，不可編造。"},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content", "")).strip()


def enhance_conclusion(question: str, hits: list["RetrievedItem"], fallback: str) -> str:
    """Use external LLM (Ollama/OpenAI) to rewrite conclusion from retrieved context."""
    if not is_enabled() or not hits:
        return fallback

    timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "8"))
    prompt = _build_prompt(question, hits)
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

    try:
        if provider == "openai":
            answer = _enhance_with_openai(prompt, timeout_seconds)
        else:
            answer = _enhance_with_ollama(prompt, timeout_seconds)
        if answer:
            return answer
    except (requests.RequestException, ValueError):
        return fallback

    return fallback
