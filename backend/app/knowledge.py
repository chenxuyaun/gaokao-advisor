"""Persistent knowledge base — survives HF Space rebuilds, avoids repeat API calls."""
import hashlib, json, os, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent.parent / "data"
KB_PATH = DATA_DIR / "knowledge.db"


def get_db():
    db = sqlite3.connect(str(KB_PATH))
    db.row_factory = sqlite3.Row
    return db


def init_kb():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT NOT NULL UNIQUE,
            major TEXT, school TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT, search_snippet TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            hit_count INTEGER DEFAULT 1,
            last_hit_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    db.execute("PRAGMA journal_mode=WAL")
    db.commit()
    db.close()


def make_hash(question: str, major: str, school: str = None) -> str:
    raw = f"{question}|{major or ''}|{school or ''}"
    return hashlib.md5(raw.encode()).hexdigest()


def lookup(question: str, major: str, school: str = None) -> Optional[dict]:
    h = make_hash(question, major, school)
    db = get_db()
    try:
        row = db.execute(
            "SELECT answer, sources, search_snippet, created_at, hit_count FROM knowledge_cache WHERE content_hash = ?",
            (h,)
        ).fetchone()
        if row:
            db.execute(
                "UPDATE knowledge_cache SET hit_count = hit_count + 1, last_hit_at = datetime('now','localtime') WHERE content_hash = ?",
                (h,)
            )
            db.commit()
            return {
                "answer": row["answer"],
                "sources": json.loads(row["sources"]) if row["sources"] else None,
                "from_cache": True,
                "cached_at": row["created_at"],
                "hit_count": row["hit_count"] + 1,
            }
        return None
    finally:
        db.close()


def store(question: str, major: str, answer: str, school: str = None,
          sources: list = None, search_snippet: str = None):
    h = make_hash(question, major, school)
    db = get_db()
    try:
        db.execute(
            """INSERT OR REPLACE INTO knowledge_cache
               (content_hash, major, school, question, answer, sources, search_snippet)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (h, major, school, question, answer,
             json.dumps(sources) if sources else None,
             search_snippet)
        )
        db.commit()
    finally:
        db.close()


def stats() -> dict:
    db = get_db()
    try:
        total = db.execute("SELECT COUNT(*) as n FROM knowledge_cache").fetchone()["n"]
        total_hits = db.execute("SELECT COALESCE(SUM(hit_count),0) as n FROM knowledge_cache").fetchone()["n"]
        recent = db.execute(
            "SELECT question, major, hit_count, created_at FROM knowledge_cache ORDER BY last_hit_at DESC LIMIT 5"
        ).fetchall()
        return {
            "total_entries": total,
            "total_hits": total_hits,
            "recent": [{"q": r["question"][:40], "major": r["major"], "hits": r["hit_count"], "at": r["created_at"]} for r in recent],
        }
    finally:
        db.close()


init_kb()
