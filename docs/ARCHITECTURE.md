# Архитектура: Система знаний команды

## Обзор

Веб-панель → FastAPI → SQLite → keyword-поиск по фрагментам → LLM (строгий JSON) → quality-gate → аудит.

```
[Browser UI]
    |  REST
[FastAPI app.main]
    |-- /kb/*     документы, ask, qa_runs, export
    |-- /ai/*     answer_with_sources
    |-- /audit/*  audit_runs
    |
[services]
    |-- kb.py      create_document, ask_knowledge_base
    |-- search.py  split snippets, keyword top-K
    |-- llm.py     ProxyAPI / offline extractive
    |-- audit.py   audited_action → audit_runs
    |
[SQLite data/knowledge.db]
    documents | snippets | qa_runs | audit_runs
```

## Поток «добавить документ»

1. `POST /kb/documents` с `title` + `text`.
2. Валидация длины (Pydantic + лимиты Settings).
3. Запись в `documents`.
4. Текст режется на абзацы → `snippets`.
5. Запись в `audit_runs` (`kb.documents.create`).

## Поток «задать вопрос»

1. `POST /kb/ask` с `question`.
2. Keyword-поиск top-K по `snippets` (стемминг, стоп-слова, порог score).
3. Если hits пустые → ответ «данных недостаточно», `needs_review=true`, пустые sources.
4. Иначе context из фрагментов → `answer_with_sources`:
   - с `LLM_API_KEY` — вызов ProxyAPI (OpenAI-compatible), JSON-ответ;
   - без ключа — offline extractive из context.
5. Quality: пустые sources / low confidence / ошибка LLM → `needs_review=true` или extractive fallback.
6. Цитаты сопоставляются с найденными snippets → `document_id`.
7. Сохранение в `qa_runs` + `audit_runs`.

## ИИ-операция

`POST /ai/answer_with_sources` — отдельный endpoint со схемой:

```json
{
  "answer": "string",
  "sources": [{"quote": "string"}],
  "confidence": "high|medium|low",
  "needs_review": true
}
```

Температура по умолчанию `0.1`. Ответ валидируется Pydantic; при сбое — fallback с `needs_review=true`.

## Память / контекст

- Долговременная: документы и snippets в SQLite.
- На запрос: top-K фрагментов как context для LLM.
- История: `qa_runs` (вопрос, ответ, sources, needs_review).
- Аудит: `audit_runs` (action, input/output, status, duration_ms).

## Ограничения (осознанные)

- Поиск keyword, не embeddings.
- Без ролей/ACL (локальная демо-панель).
- Документы — raw text, не PDF.
- Без ключа LLM работает offline extractive-режим.
