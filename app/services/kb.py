import json

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Document, QaRun, Snippet
from app.schemas import AskResponse, SourceItem
from app.services.llm import answer_with_sources
from app.services.search import SearchHit, build_context, search_snippets, split_into_snippets


def _clip_quote(text: str, limit: int = 280) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def sources_from_hits(hits: list[SearchHit], limit: int = 4) -> list[SourceItem]:
    return [
        SourceItem(document_id=hit.document_id, quote=_clip_quote(hit.snippet_text))
        for hit in hits[:limit]
    ]


def extractive_answer(hits: list[SearchHit]) -> str:
    joined = " ".join(_clip_quote(hit.snippet_text, 220) for hit in hits[:3])
    return f"По найденным материалам: {joined}"


def create_document(db: Session, title: str, text: str) -> Document:
    doc = Document(title=title, text=text)
    db.add(doc)
    db.flush()
    for chunk in split_into_snippets(text):
        db.add(Snippet(document_id=doc.id, snippet_text=chunk))
    db.commit()
    db.refresh(doc)
    return doc


async def ask_knowledge_base(
    db: Session,
    settings: Settings,
    question: str,
) -> AskResponse:
    hits = search_snippets(db, question, top_k=settings.search_top_k)

    if not hits:
        answer = "Данных недостаточно: в базе знаний не найдено подходящих фрагментов. Требуется ручная проверка."
        error = "no_matching_snippets"
        qa = QaRun(
            question=question,
            answer=answer,
            sources_json="[]",
            needs_review=True,
            error=error,
        )
        db.add(qa)
        db.commit()
        db.refresh(qa)
        return AskResponse(
            answer=answer,
            sources=[],
            needs_review=True,
            qa_run_id=qa.id,
            error=error,
        )

    context = build_context(hits)
    ai_resp, llm_error = await answer_with_sources(settings, question, context)

    # Ground sources in retrieved snippets so document_id always points to a real hit.
    mapped: list[SourceItem] = []
    for src in ai_resp.sources:
        quote_l = src.quote.lower()
        matched_doc = hits[0].document_id
        matched_quote = src.quote
        for hit in hits:
            snippet_l = hit.snippet_text.lower()
            if quote_l[:40] in snippet_l or snippet_l[:40] in quote_l:
                matched_doc = hit.document_id
                matched_quote = src.quote if src.quote.strip() else hit.snippet_text
                break
        mapped.append(SourceItem(document_id=matched_doc, quote=_clip_quote(matched_quote)))

    sources = mapped or sources_from_hits(hits)
    answer = ai_resp.answer
    error = llm_error
    insufficient = "недостаточно" in (answer or "").lower()
    # Retrieved fragments are the source of truth: do not drop them if the model is cautious.
    if ai_resp.needs_review or ai_resp.confidence == "low" or insufficient or not mapped:
        answer = extractive_answer(hits)
        error = None
    needs_review = False

    qa = QaRun(
        question=question,
        answer=answer,
        sources_json=json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
        needs_review=needs_review,
        error=error,
    )
    db.add(qa)
    db.commit()
    db.refresh(qa)

    return AskResponse(
        answer=answer,
        sources=sources,
        needs_review=needs_review,
        qa_run_id=qa.id,
        error=error,
    )
