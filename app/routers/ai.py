from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.schemas import AiAnswerRequest, AiAnswerResponse
from app.services.audit import audited_action
from app.services.llm import answer_with_sources

router = APIRouter(tags=["ai"])


@router.post("/ai/answer_with_sources", response_model=AiAnswerResponse)
async def ai_answer_with_sources(
    body: AiAnswerRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AiAnswerResponse:
    with audited_action(db, "ai.answer_with_sources", body.model_dump()) as ctx:
        result, error = await answer_with_sources(settings, body.question, body.context)
        ctx["output"] = result.model_dump()
        if result.needs_review:
            ctx["status"] = "needs_review"
            ctx["error"] = error or "needs_review"
        elif error:
            ctx["error"] = error
        return result
