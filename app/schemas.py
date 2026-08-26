from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    text: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("title", "text")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class DocumentListItem(BaseModel):
    id: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentListItem):
    text: str


class DocumentCreateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    document_id: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class SourceItem(BaseModel):
    document_id: str
    quote: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    needs_review: bool
    qa_run_id: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def empty_sources_require_review(self):
        if not self.sources:
            self.needs_review = True
        return self


class AiSourceItem(BaseModel):
    quote: str


class AiAnswerRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)

    @field_validator("question", "context")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class AiAnswerResponse(BaseModel):
    answer: str
    sources: list[AiSourceItem]
    confidence: Literal["high", "medium", "low"]
    needs_review: bool


class QaRunListItem(BaseModel):
    id: str
    created_at: datetime
    question: str
    needs_review: bool

    model_config = {"from_attributes": True}


class QaRunDetail(QaRunListItem):
    answer: str
    sources: list[SourceItem]
    error: str | None = None


class AuditRunItem(BaseModel):
    id: str
    created_at: datetime
    action: str
    input: str
    output: str
    status: str
    error: str | None
    duration_ms: int

    model_config = {"from_attributes": True}
