"""Core recommendation engine — rank estimation and cutoff scores."""
from typing import Optional
from app.database import get_db


async def estimate_rank(province: str, score: int, category: str, year: int = 2026) -> Optional[int]:
    """Estimate province rank from score using 一分一段表 with linear interpolation."""
    db = await get_db()
    try:
        # Exact match first
        cursor = await db.execute(
            """SELECT cumulative_count FROM score_segments
               WHERE province_name = ? AND year = ? AND category = ? AND score = ?""",
            (province, year, category, score)
        )
        row = await cursor.fetchone()
        if row and row[0] is not None:
            return row[0]

        # Get nearest upper and lower points for interpolation
        cursor = await db.execute(
            """SELECT score, cumulative_count FROM score_segments
               WHERE province_name = ? AND year = ? AND category = ? AND score >= ?
               AND cumulative_count IS NOT NULL
               ORDER BY score ASC LIMIT 1""",
            (province, year, category, score)
        )
        upper = await cursor.fetchone()

        cursor = await db.execute(
            """SELECT score, cumulative_count FROM score_segments
               WHERE province_name = ? AND year = ? AND category = ? AND score <= ?
               AND cumulative_count IS NOT NULL
               ORDER BY score DESC LIMIT 1""",
            (province, year, category, score)
        )
        lower = await cursor.fetchone()

        if upper and lower:
            if upper[0] == lower[0]:
                return lower[1]
            # Linear interpolation
            ratio = (score - lower[0]) / (upper[0] - lower[0])
            est = int(lower[1] + (upper[1] - lower[1]) * ratio)
            return est
        elif upper:
            return upper[1]
        elif lower:
            return lower[1]
        return None
    finally:
        await db.close()


# Legacy: simple matching function (still used by v2)
async def match_majors(province: str, category: str, subject_combo: str,
                       estimated_rank: int, reference_year: int = 2025,
                       min_quality_score: int = 65, max_results: int = 12) -> list:
    """Legacy matching - kept for v2 compatibility."""
    import json
    # Return empty - v2 will fall through to basic recommendations
    return []


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
