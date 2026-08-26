"""Run kb_questions against local API expectations (smoke)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.services.kb import ask_knowledge_base, create_document
from sqlalchemy import select
from app.models import Document


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=Path, default=ROOT / "tests_data" / "kb_documents.jsonl")
    parser.add_argument("--questions", type=Path, default=ROOT / "tests_data" / "kb_questions.jsonl")
    args = parser.parse_args()

    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        if not db.scalars(select(Document)).first():
            for item in load_jsonl(args.documents):
                create_document(db, item["title"], item["text"])

        failed = 0
        for idx, item in enumerate(load_jsonl(args.questions), start=1):
            result = await ask_knowledge_base(db, settings, item["question"])
            expected = bool(item["expected_needs_review"])
            ok = result.needs_review is expected
            if expected is False and not result.sources:
                ok = False
            mark = "OK" if ok else "FAIL"
            if not ok:
                failed += 1
            print(
                f"{idx:02d} [{mark}] needs_review={result.needs_review} "
                f"expected={expected} sources={len(result.sources)} :: {item['question']}"
            )
        if failed:
            raise SystemExit(f"failed: {failed}")
        print("all questions matched expectations")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
