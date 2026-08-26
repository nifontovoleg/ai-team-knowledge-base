import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Snippet


_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_]+", re.UNICODE)

# Lightweight RU/EN stopwords so generic question words don't create false hits.
_STOPWORDS = {
    "а",
    "и",
    "или",
    "но",
    "да",
    "нет",
    "не",
    "ни",
    "на",
    "в",
    "во",
    "к",
    "ко",
    "о",
    "об",
    "обо",
    "от",
    "до",
    "по",
    "за",
    "из",
    "у",
    "с",
    "со",
    "для",
    "при",
    "про",
    "как",
    "какой",
    "какая",
    "какие",
    "каким",
    "какое",
    "что",
    "чем",
    "чего",
    "где",
    "когда",
    "кто",
    "кого",
    "кому",
    "чей",
    "чья",
    "чьё",
    "это",
    "этот",
    "эта",
    "эти",
    "тот",
    "та",
    "те",
    "ли",
    "же",
    "бы",
    "был",
    "была",
    "было",
    "были",
    "есть",
    "быть",
    "можно",
    "нужно",
    "надо",
    "уже",
    "ещё",
    "еще",
    "очень",
    "также",
    "тоже",
    "если",
    "чтобы",
    "только",
    "между",
    "через",
    "после",
    "перед",
    "без",
    "над",
    "под",
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "with",
    "by",
    "from",
    "at",
    "as",
    "it",
    "this",
    "that",
    "what",
    "which",
    "who",
    "where",
    "when",
    "how",
    "why",
}


def stem_token(token: str) -> str:
    """Very light RU/EN stemmer for keyword overlap."""
    if len(token) <= 3:
        return token
    for suffix in (
        "ами",
        "ями",
        "иями",
        "ов",
        "ев",
        "ей",
        "ом",
        "ем",
        "ах",
        "ях",
        "ую",
        "юю",
        "ая",
        "яя",
        "ые",
        "ие",
        "ых",
        "их",
        "ым",
        "им",
        "ой",
        "ий",
        "ый",
        "ть",
        "ти",
        "ing",
        "ed",
        "es",
        "s",
        "а",
        "я",
        "у",
        "ю",
        "е",
        "и",
        "о",
        "ы",
    ):
        if len(token) - len(suffix) >= 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> set[str]:
    return {stem_token(m.group(0).lower()) for m in _TOKEN_RE.finditer(text)}


def meaningful_tokens(text: str) -> set[str]:
    tokens = set()
    for raw in (m.group(0).lower() for m in _TOKEN_RE.finditer(text)):
        if raw in _STOPWORDS or len(raw) <= 2:
            continue
        stemmed = stem_token(raw)
        if stemmed in _STOPWORDS or len(stemmed) <= 2:
            continue
        tokens.add(stemmed)
    return tokens


def split_into_snippets(text: str, min_len: int = 40) -> list[str]:
    parts = re.split(r"\n\s*\n+", text.strip())
    snippets: list[str] = []
    buffer = ""
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        if not buffer:
            buffer = cleaned
            continue
        # Keep short headings attached to the following paragraph.
        if len(buffer) < min_len:
            buffer = f"{buffer}\n\n{cleaned}"
            continue
        snippets.append(buffer)
        buffer = cleaned
    if buffer:
        snippets.append(buffer)
    if not snippets and text.strip():
        snippets = [text.strip()]
    return snippets


@dataclass
class SearchHit:
    document_id: str
    snippet_id: str
    snippet_text: str
    score: float


def search_snippets(
    db: Session,
    question: str,
    top_k: int = 5,
    min_score: float = 0.34,
    min_overlap: int = 2,
) -> list[SearchHit]:
    q_tokens = meaningful_tokens(question)
    if not q_tokens:
        return []

    rows = db.scalars(select(Snippet).options(joinedload(Snippet.document))).all()
    title_coverage: dict[str, float] = {}
    for row in rows:
        if row.document_id in title_coverage:
            continue
        title_tokens = meaningful_tokens(row.document.title if row.document else "")
        if not title_tokens:
            title_coverage[row.document_id] = 0.0
            continue
        title_coverage[row.document_id] = len(q_tokens & title_tokens) / max(len(title_tokens), 1)

    hits: list[SearchHit] = []
    for row in rows:
        s_tokens = meaningful_tokens(row.snippet_text)
        if not s_tokens:
            continue
        overlap = q_tokens & s_tokens
        title_cov = title_coverage.get(row.document_id, 0.0)
        strong_doc = title_cov >= 0.5
        if not overlap:
            continue
        # Rare/long tokens (e.g. needs_review, стендап) are stronger signals.
        weighted = 0.0
        for token in overlap:
            weighted += 1.6 if len(token) >= 8 else 1.0
        score = weighted / max(len(q_tokens), 1) + title_cov * 0.6
        coverage = len(overlap) / max(len(q_tokens), 1)
        strong = any(len(t) >= 6 for t in overlap)
        # Title match lets us keep step-paragraphs from the right document.
        if strong_doc:
            pass
        elif len(overlap) >= min_overlap and coverage >= 0.34:
            pass
        elif strong and score >= 0.22 and len(overlap) >= 1 and coverage >= 0.2:
            pass
        else:
            continue
        if not strong_doc and score < min_score and not (strong and coverage >= 0.2):
            continue
        hits.append(
            SearchHit(
                document_id=row.document_id,
                snippet_id=row.id,
                snippet_text=row.snippet_text,
                score=score,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    # Drop weak tail relative to best hit (do not re-apply absolute min_score here).
    if hits:
        best = hits[0].score
        hits = [h for h in hits if h.score >= best * 0.4]
    return hits[:top_k]


def build_context(hits: list[SearchHit]) -> str:
    blocks: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        blocks.append(
            f"[source {idx} | document_id={hit.document_id}]\n{hit.snippet_text}"
        )
    return "\n\n".join(blocks)
