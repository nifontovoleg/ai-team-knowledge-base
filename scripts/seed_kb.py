"""Load tests_data into SQLite knowledge base."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Document
from app.services.kb import create_document


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed KB documents from tests_data")
    parser.add_argument(
        "--documents",
        type=Path,
        default=ROOT / "tests_data" / "kb_documents.jsonl",
    )
    parser.add_argument("--force", action="store_true", help="Load even if documents already exist")
    args = parser.parse_args()

    init_db()
    docs = load_jsonl(args.documents)
    db = SessionLocal()
    try:
        existing = db.scalars(select(Document)).first()
        if existing and not args.force:
            print("Documents already present. Use --force to add again.")
            return
        for item in docs:
            doc = create_document(db, item["title"], item["text"])
            print(f"loaded: {doc.id} | {doc.title}")
        print(f"done: {len(docs)} documents")
    finally:
        db.close()


if __name__ == "__main__":
    main()
