"""Core recommendation engine — rank estimation + tiered matching."""
from typing import List, Tuple, Optional
from app.database import get_db


async def estimate_rank(province: str, score: int, category: str, year: int = 2026) -> Optional[int]:
    """Estimate province rank from score using 一分一段表."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT cumulative_count FROM score_segments
               WHERE province_name = ? AND year = ? AND category = ? AND score = ?""",
            (province, year, category, score)
        )
        row = await cursor.fetchone()
        if row:
            return row[0]
        for delta in range(1, 6):
            cursor = await db.execute(
                """SELECT cumulative_count FROM score_segments
                   WHERE province_name = ? AND year = ? AND category = ? AND score = ?""",
                (province, year, category, score + delta)
            )
            row = await cursor.fetchone()
            if row: return row[1]
            cursor = await db.execute(
                """SELECT cumulative_count FROM score_segments
                   WHERE province_name = ? AND year = ? AND category = ? AND score = ?""",
                (province, year, category, score - delta)
            )
            row = await cursor.fetchone()
            if row: return row[1]
        return None
    finally:
        await db.close()


async def match_universities(
    province: str,
    category: str,
    subject_combo: str,
    estimated_rank: int,
    prefer_city: Optional[str] = None,
    prefer_major_category: Optional[str] = None,
    max_tuition: Optional[int] = None,
    reference_year: int = 2025,
    rush_ratio: float = 0.97,
    safe_ratio: float = 1.05,
    floor_ratio: float = 0.85,
    ceiling_ratio: float = 1.30,
) -> List[dict]:
    """Match universities using tiered strategy (冲/稳/保)."""
    db = await get_db()
    try:
        has_chem = "化" in subject_combo
        has_bio = "生" in subject_combo

        results = []

        query = """
            SELECT u.id, u.name, u.level, u.city,
                   ar.group_name, ar.min_score, ar.min_rank,
                   ar.subject_requirement, ar.major_category,
                   ar.tuition, ar.is_sino_foreign,
                   ar.source, ar.confidence, ar.notes
            FROM admission_records ar
            JOIN universities u ON ar.university_id = u.id
            WHERE ar.target_province = ?
              AND ar.category = ?
              AND ar.year = ?
        """
        params = [province, category, reference_year]

        if prefer_city:
            query += " AND u.city LIKE ?"
            params.append(f"%{prefer_city}%")
        if prefer_major_category:
            query += " AND ar.major_category LIKE ?"
            params.append(f"%{prefer_major_category}%")
        if max_tuition:
            query += " AND ar.tuition <= ?"
            params.append(max_tuition)

        query += " ORDER BY ar.min_rank ASC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        for row in rows:
            min_rank = row[6]
            if min_rank is None:
                continue

            result = {
                "id": row[0],
                "name": row[1],
                "level": row[2],
                "city": row[3],
                "group_name": row[4],
                "min_score": row[5],
                "min_rank": min_rank,
                "subject_requirement": row[7],
                "major_category": row[8],
                "tuition": row[9],
                "is_sino_foreign": bool(row[10]),
                "source": row[11] or "2025录取数据",
                "confidence": row[12] or "MEDIUM",
                "notes": row[13],
            }

            # Filter by subject requirement
            req = row[7] or ""
            if "化学" in req and not has_chem:
                continue
            if "生物" in req and not has_bio:
                continue

            # Classify tier
            ratio = min_rank / estimated_rank if estimated_rank else 1.0
            if ratio < floor_ratio:
                continue
            elif ratio < rush_ratio:
                result["tier"] = "冲刺"
            elif ratio <= safe_ratio:
                result["tier"] = "稳妥"
            elif ratio <= ceiling_ratio:
                result["tier"] = "保底"
            else:
                continue

            # Attach major details if category matches
            if result["major_category"]:
                major_cursor = await db.execute(
                    """SELECT avg_salary_5yr, employment_rate, career_path, zhang_xuefeng_comment
                       FROM majors WHERE category = ? OR name LIKE ? LIMIT 1""",
                    (result["major_category"], f"%{result['major_category']}%")
                )
                major_row = await major_cursor.fetchone()
                if major_row:
                    result["avg_salary"] = major_row[0]
                    result["employment_rate"] = major_row[1]
                    result["career_path"] = major_row[2]
                    result["zhang_xuefeng_comment"] = major_row[3]

            results.append(result)

        return results
    finally:
        await db.close()


async def get_cutoff_scores(province: str, year: int, category: str) -> dict:
    """Get provincial cutoff scores."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT batch, score FROM provinces
               WHERE name = ? AND year = ? AND category = ?""",
            (province, year, category)
        )
        rows = await cursor.fetchall()
        result = {}
        for row in rows:
            result[row[0]] = row[1]
        return result
    finally:
        await db.close()
