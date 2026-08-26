import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas import AiAnswerResponse, AiSourceItem


SYSTEM_PROMPT = """Ты — помощник по базе знаний команды.
Отвечай ТОЛЬКО на основе переданного context.
Не выдумывай факты. Если данных недостаточно — так и скажи.
Верни ТОЛЬКО валидный JSON без markdown и пояснений со схемой:
{
  "answer": "string",
  "sources": [{"quote": "string"}],
  "confidence": "high" | "medium" | "low",
  "needs_review": boolean
}
Правила:
- quote должен быть короткой цитатой из context;
- если context пустой или не относится к вопросу: answer про "данных недостаточно", sources=[], confidence="low", needs_review=true;
- если уверенность низкая: needs_review=true.
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _fallback_low_confidence(reason: str) -> AiAnswerResponse:
    return AiAnswerResponse(
        answer="Данных недостаточно для уверенного ответа. Требуется ручная проверка.",
        sources=[],
        confidence="low",
        needs_review=True,
    )


async def answer_with_sources(
    settings: Settings,
    question: str,
    context: str,
) -> tuple[AiAnswerResponse, str | None]:
    """Returns (response, error_reason)."""
    if not context.strip():
        return _fallback_low_confidence("empty_context"), "empty_context"

    if not settings.llm_api_key:
        # Offline/dev fallback: extractive answer from context blocks.
        quotes: list[AiSourceItem] = []
        bodies: list[str] = []
        for block in context.split("\n\n"):
            lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            body = "\n".join(ln for ln in lines if not ln.startswith("[source"))
            if body:
                quotes.append(AiSourceItem(quote=body[:240]))
                bodies.append(body)
            if len(quotes) >= 3:
                break
        if not quotes:
            return _fallback_low_confidence("no_quotes"), "no_llm_key_and_no_quotes"
        joined = " ".join(bodies)
        answer = (
            "По найденным материалам: "
            + (joined[:500] + ("…" if len(joined) > 500 else ""))
            + " (offline-режим без LLM_API_KEY)."
        )
        resp = AiAnswerResponse(
            answer=answer,
            sources=quotes,
            confidence="medium",
            needs_review=False,
        )
        return _normalize_quality(resp), None

    payload = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"question:\n{question}\n\ncontext:\n{context}",
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            validated = AiAnswerResponse.model_validate(parsed)
            return _normalize_quality(validated), None
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        fallback = _fallback_low_confidence(str(exc))
        return fallback, f"llm_error: {exc}"


def _normalize_quality(resp: AiAnswerResponse) -> AiAnswerResponse:
    sources = [s for s in resp.sources if s.quote and s.quote.strip()]
    needs_review = resp.needs_review
    answer = resp.answer
    confidence = resp.confidence

    if not sources:
        needs_review = True
        confidence = "low"
        if "недостаточно" not in answer.lower():
            answer = "Данных недостаточно для уверенного ответа. Требуется ручная проверка."

    if confidence == "low":
        needs_review = True

    if needs_review and not sources and "недостаточно" not in answer.lower():
        answer = "Данных недостаточно для уверенного ответа. Требуется ручная проверка."

    return AiAnswerResponse(
        answer=answer,
        sources=sources,
        confidence=confidence,
        needs_review=needs_review,
    )
