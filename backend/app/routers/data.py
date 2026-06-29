"""Data query API router."""
from fastapi import APIRouter, Query
from app.database import get_db

router = APIRouter()


@router.get("/provinces")
async def list_provinces(year: int = 2026):
    """Get all provinces and their cutoff scores."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT DISTINCT name, category, batch, score FROM provinces WHERE year = ? ORDER BY name, category",
            (year,)
        )
        rows = await cursor.fetchall()
        return [
            {"name": r[0], "category": r[1], "batch": r[2], "score": r[3]}
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/rank/{province}/{score}")
async def get_rank(
    province: str,
    score: int,
    category: str = "物理类",
    year: int = 2026,
):
    """Get estimated rank for a score."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT score, cumulative_count, section_count
               FROM score_segments
               WHERE province_name = ? AND year = ? AND category = ? AND score = ?""",
            (province, year, category, score)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "province": province,
                "score": row[0],
                "cumulative_count": row[1],
                "section_count": row[2],
                "year": year,
                "category": category,
            }
        return {"error": "未找到该分数对应的位次数据", "province": province, "score": score}
    finally:
        await db.close()


@router.get("/score-segments/{province}")
async def get_score_segments(
    province: str,
    year: int = 2026,
    category: str = "物理类",
    min_score: int = Query(400, ge=0, le=750),
    max_score: int = Query(750, ge=0, le=750),
):
    """Get score distribution table."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT score, cumulative_count, section_count
               FROM score_segments
               WHERE province_name = ? AND year = ? AND category = ?
               AND score BETWEEN ? AND ?
               ORDER BY score DESC""",
            (province, year, category, min_score, max_score)
        )
        rows = await cursor.fetchall()
        return [
            {"score": r[0], "cumulative_count": r[1], "section_count": r[2]}
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/universities")
async def list_universities(province: str = None, level: str = None):
    """List universities with optional filters."""
    db = await get_db()
    try:
        query = "SELECT id, name, level, province, city, website FROM universities WHERE 1=1"
        params = []
        if province:
            query += " AND province LIKE ?"
            params.append(f"%{province}%")
        if level:
            query += " AND level = ?"
            params.append(level)
        query += " ORDER BY name"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "name": r[1], "level": r[2], "province": r[3], "city": r[4], "website": r[5]}
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/university/{university_id}")
async def get_university(university_id: int):
    """Get university details with admission history."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, level, province, city, website FROM universities WHERE id = ?",
            (university_id,)
        )
        uni = await cursor.fetchone()
        if not uni:
            return {"error": "未找到该院校"}

        cursor = await db.execute(
            """SELECT year, target_province, category, group_name,
                      min_score, min_rank, subject_requirement, major_category, tuition
               FROM admission_records WHERE university_id = ?
               ORDER BY year DESC""",
            (university_id,)
        )
        admissions = [
            {
                "year": r[0], "target_province": r[1], "category": r[2],
                "group_name": r[3], "min_score": r[4], "min_rank": r[5],
                "subject_requirement": r[6], "major_category": r[7], "tuition": r[8],
            }
            for r in await cursor.fetchall()
        ]

        return {
            "id": uni[0], "name": uni[1], "level": uni[2],
            "province": uni[3], "city": uni[4], "website": uni[5],
            "admissions": admissions,
        }
    finally:
        await db.close()


@router.get("/majors")
async def list_majors(category: str = None):
    """List majors with career data."""
    db = await get_db()
    try:
        query = "SELECT id, name, category, subject_requirements, avg_salary_5yr, employment_rate, career_path, zhang_xuefeng_comment FROM majors"
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY category, name"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "name": r[1], "category": r[2],
                "subject_requirements": r[3], "avg_salary_5yr": r[4],
                "employment_rate": r[5], "career_path": r[6],
                "zhang_xuefeng_comment": r[7],
            }
            for r in rows
        ]
    finally:
        await db.close()
