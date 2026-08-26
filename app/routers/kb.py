import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Document, QaRun
from app.schemas import (
    AskRequest,
    AskResponse,
    DocumentCreate,
    DocumentCreateResponse,
    DocumentDetail,
    DocumentListItem,
    QaRunDetail,
    QaRunListItem,
    SourceItem,
)
from app.services.audit import audited_action
from app.services.kb import ask_knowledge_base, create_document

router = APIRouter(tags=["kb"])


@router.post("/kb/documents", response_model=DocumentCreateResponse)
def add_document(
    body: DocumentCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentCreateResponse:
    if len(body.title) > settings.max_title_length:
        raise HTTPException(status_code=422, detail="title too long")
    if len(body.text) > settings.max_text_length:
        raise HTTPException(status_code=422, detail="text too long")

    with audited_action(db, "kb.documents.create", body.model_dump()) as ctx:
        doc = create_document(db, body.title, body.text)
        result = DocumentCreateResponse(document_id=doc.id)
        ctx["output"] = result.model_dump()
        return result


@router.get("/kb/documents", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    rows = db.scalars(select(Document).order_by(Document.created_at.desc())).all()
    return list(rows)


@router.get("/kb/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.post("/kb/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    if len(body.question) > settings.max_question_length:
        raise HTTPException(status_code=422, detail="question too long")

    with audited_action(db, "kb.ask", body.model_dump()) as ctx:
        result = await ask_knowledge_base(db, settings, body.question)
        ctx["output"] = result.model_dump()
        if result.needs_review:
            ctx["status"] = "needs_review"
            ctx["error"] = result.error or "needs_review"
        return result


@router.get("/qa/runs", response_model=list[QaRunListItem])
def list_qa_runs(
    needs_review: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[QaRun]:
    stmt = select(QaRun).order_by(QaRun.created_at.desc()).limit(limit)
    if needs_review is not None:
        stmt = (
            select(QaRun)
            .where(QaRun.needs_review.is_(needs_review))
            .order_by(QaRun.created_at.desc())
            .limit(limit)
        )
    return list(db.scalars(stmt).all())


@router.get("/qa/runs/{qa_run_id}", response_model=QaRunDetail)
def get_qa_run(qa_run_id: str, db: Session = Depends(get_db)) -> QaRunDetail:
    row = db.get(QaRun, qa_run_id)
    if not row:
        raise HTTPException(status_code=404, detail="qa_run not found")
    sources_raw = json.loads(row.sources_json or "[]")
    sources = [SourceItem.model_validate(item) for item in sources_raw]
    return QaRunDetail(
        id=row.id,
        created_at=row.created_at,
        question=row.question,
        needs_review=row.needs_review,
        answer=row.answer,
        sources=sources,
        error=row.error,
    )


@router.get("/export/qa")
def export_qa(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
) -> Response:
    rows = db.scalars(select(QaRun).order_by(QaRun.created_at.desc()).limit(200)).all()
    if format == "csv":
        buffer = io.StringIO()
        # Excel (RU) expects ';' and UTF-8 BOM; otherwise columns and Cyrillic look like garbage.
        writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow(
            [
                "id",
                "дата",
                "вопрос",
                "ответ",
                "требует_проверки",
                "причина",
                "источники",
            ]
        )
        for row in rows:
            sources_raw = json.loads(row.sources_json or "[]")
            sources_readable = " | ".join(
                f"{(item.get('quote') or '').replace(chr(10), ' ').replace(chr(13), ' ').strip()}"
                f" [{item.get('document_id', '')}]"
                for item in sources_raw
                if isinstance(item, dict)
            )
            writer.writerow(
                [
                    row.id,
                    row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else "",
                    _csv_cell(row.question),
                    _csv_cell(row.answer),
                    "да" if row.needs_review else "нет",
                    _csv_cell(row.error or ""),
                    _csv_cell(sources_readable),
                ]
            )
        # BOM so Excel recognizes UTF-8
        content = "\ufeff" + buffer.getvalue()
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=qa_runs.csv"},
        )

    payload = [
        {
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "question": row.question,
            "answer": row.answer,
            "needs_review": row.needs_review,
            "error": row.error,
            "sources": json.loads(row.sources_json or "[]"),
        }
        for row in rows
    ]
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=qa_runs.json"},
    )


def _csv_cell(value: str) -> str:
    return " ".join(str(value or "").replace("\r", " ").splitlines()).strip()
