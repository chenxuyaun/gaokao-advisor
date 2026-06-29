"""Database connection and initialization."""
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "gaokao.db"


async def get_db():
    """Get async database connection."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await get_db()
    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS provinces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            year INTEGER NOT NULL,
            category TEXT NOT NULL,
            batch TEXT NOT NULL,
            score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, year, category, batch)
        );

        CREATE TABLE IF NOT EXISTS score_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province_name TEXT NOT NULL,
            year INTEGER NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            cumulative_count INTEGER,
            section_count INTEGER,
            UNIQUE(province_name, year, category, score)
        );

        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT,
            level TEXT,
            province TEXT,
            city TEXT,
            is_public BOOLEAN DEFAULT 1,
            website TEXT
        );

        CREATE TABLE IF NOT EXISTS admission_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER REFERENCES universities(id),
            year INTEGER NOT NULL,
            target_province TEXT NOT NULL,
            category TEXT NOT NULL,
            subject_requirement TEXT,
            group_name TEXT,
            min_score INTEGER NOT NULL,
            min_rank INTEGER,
            avg_score INTEGER,
            major_category TEXT,
            tuition INTEGER,
            is_sino_foreign BOOLEAN DEFAULT 0,
            source TEXT DEFAULT '2025录取数据',
            confidence TEXT DEFAULT 'HIGH',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            subject_requirements TEXT,
            avg_salary_5yr INTEGER,
            employment_rate REAL,
            career_path TEXT,
            zhang_xuefeng_comment TEXT
        );
        """)
        await db.commit()
        print(f"[DB] Initialized at {DB_PATH}")
    finally:
        await db.close()
