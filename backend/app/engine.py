"""Core recommendation engine v2 — major-first, quality-scored, career-aware."""
from typing import List, Tuple, Optional, Dict
from app.database import get_db


# === Quality scoring for majors ===
# Maps each major to: (base_score, 考公_bonus, growth_bonus, tags)
MAJOR_QUALITY = {
    "临床医学":     (95, 15, 5,  ["越老越值钱", "考公对口卫健委/医保局", "终身职业"]),
    "口腔医学":     (93, 10, 5,  ["可单干创业", "考公对口卫健委", "收入天花板高"]),
    "麻醉学":       (90, 12, 3,  ["刚需科室", "工作强度<临床", "考公对口"]),
    "医学影像学":   (85, 12, 3,  ["AI冲击可控", "体检中心需求大", "考公对口"]),
    "药学":         (78, 10, 3,  ["药企研发/医院药剂科", "考公对口药监局", "稳定"]),
    "人工智能":     (88, 5,  20, ["风口行业", "考公对口工信局/大数据局", "建议读研"]),
    "数据科学":     (85, 8,  15, ["数字时代核心", "考公可报统计局/大数据局", "生物信息交叉稀缺"]),
    "大数据":       (82, 8,  15, ["企业需求大", "考公对口统计局", "本科够用"]),
    "计算机":       (82, 8,  12, ["万金油", "考公岗位多", "考编容易"]),
    "软件工程":     (80, 6,  12, ["互联网主力", "考公可报信息中心", "35岁风险注意"]),
    "电气工程":     (85, 10, 10, ["国家电网对口", "考公可报电力系统", "央企稳定"]),
    "自动化":       (80, 6,  10, ["智能制造", "考公可报工信局", "工科基础好"]),
    "新能源":       (82, 5,  15, ["双碳战略核心", "宁德时代/比亚迪", "朝阳产业"]),
    "化学工程":     (70, 8,  5,  ["国民支柱产业", "万华化学等", "本科薪资偏低"]),
    "材料科学":     (65, 5,  8,  ["四大天王之一", "建议读研", "本科就业薪资偏低"]),
    "通信工程":     (80, 6,  10, ["5G/6G方向", "华为中兴", "考公可报通管局"]),
    "电子信息":     (82, 6,  12, ["芯片/半导体", "国家战略", "考公可报工信局"]),
    "法学":         (75, 18, 3,  ["考公王者", "法检/司法局大量招", "需过法考"]),
    "会计/审计":    (78, 15, 3,  ["考公大户", "财政局/审计局/税务局", "越老越值钱"]),
    "金融/经管":    (72, 12, 5,  ["考公可报银保监/证监", "银行/券商", "名校加成重要"]),
    "师范":         (75, 15, 2,  ["考编容易", "教师有寒暑假", "稳定"]),
    "大气科学":     (76, 10, 5,  ["气象局对口", "冷门但就业确定", "双一流"]),
    "核工程":       (80, 10, 8,  ["中核/中广核", "体制内就业", "稀缺专业"]),
    "石油/地质":    (75, 10, 3,  ["三桶油", "国企稳定", "考公可报自然资源局"]),
    "土木/交通":    (65, 10, 3,  ["基建需求", "考公可报交通局", "工作环境考虑"]),
    "环境科学":     (60, 8,  8,  ["双碳利好", "环保局对口", "薪资天花板明显"]),
    "生物科学":     (58, 5,  8,  ["主要读博", "本科就业难", "不推荐本科直接就业"]),
    "食品科学":     (65, 5,  2,  ["稳定偏保守", "市场监管对口", "适合求稳"]),
    "外语/经管":    (68, 8,  3,  ["外企/翻译", "考公外交部/商务局", "AI翻译冲击"]),
    "综合/工科":    (72, 5,  5,  ["通用工科", "看具体方向", "985/211加持重要"]),
    "综合/师范":    (75, 12, 2,  ["211师范", "考编优势", "稳定"]),
    "综合类":       (70, 8,  3,  ["看具体专业方向", "985/211名头重要", "选调生资格"]),
}

# 考公岗位对照表
CIVIL_SERVICE_MAP = {
    "医学":   "卫健委、疾控中心、药监局、医保局",
    "工学":   "工信局、住建局、交通局、大数据局",
    "理学":   "统计局、气象局、地震局、环保局",
    "法学":   "法院、检察院、司法局、公安局",
    "经管":   "财政局、审计局、税务局、发改委",
    "师范":   "教育局、中小学教师编（事业编）",
}


def score_major(major_category: str) -> Tuple[int, str, str]:
    """Return (quality_score out of 100, civil_service_note, growth_note)."""
    for key, (base, civil, growth, tags) in MAJOR_QUALITY.items():
        if key in major_category:
            civil_note = CIVIL_SERVICE_MAP.get(
                _map_category(key, major_category), "考公可报考对口岗位"
            )
            growth_note = "、".join(tags[:3])
            return (base + civil + growth, civil_note, growth_note)
    # Default for unknown majors
    return (65, "考公一般岗位", "建议具体查询该专业就业前景")


def _map_category(major_name: str, full_category: str) -> str:
    if "医" in major_name or "药" in major_name:
        return "医学"
    if "师范" in major_name or "师范" in full_category:
        return "师范"
    if "法" in full_category or "法学" in major_name:
        return "法学"
    if "会计" in full_category or "审计" in full_category or "经管" in full_category or "财经" in full_category:
        return "经管"
    if "生物" in full_category or "化学" in full_category:
        return "理学"
    return "工学"


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


async def match_majors(
    province: str,
    category: str,
    subject_combo: str,
    estimated_rank: int,
    reference_year: int = 2025,
    min_quality_score: int = 65,
    max_results: int = 12,
) -> List[dict]:
    """Match by MAJOR first: group schools under each major, filter by quality and career value."""
    db = await get_db()
    try:
        has_chem = "化" in subject_combo
        has_bio = "生" in subject_combo

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
            ORDER BY ar.min_rank ASC
        """
        cursor = await db.execute(query, [province, category, reference_year])
        rows = await cursor.fetchall()

        # Phase 1: Score and filter all matches
        major_groups: Dict[str, dict] = {}  # major_category → {quality, schools: [...]}

        for row in rows:
            min_rank = row[6]
            if min_rank is None:
                continue

            # Subject requirement filter
            req = row[7] or ""
            if "化学" in req and not has_chem:
                continue
            if "生物" in req and not has_bio:
                continue

            # Rank ratio filter
            ratio = min_rank / estimated_rank if estimated_rank else 1.0
            if ratio < 0.85 or ratio > 1.30:
                continue

            # Tier
            if ratio < 0.97:
                tier = "冲刺"
            elif ratio <= 1.05:
                tier = "稳妥"
            else:
                tier = "保底"

            major_cat = row[8] or "综合类"

            # Score the major
            q_score, civil_note, growth_note = score_major(major_cat)

            # Only include if quality score meets threshold
            if q_score < min_quality_score:
                continue

            school_info = {
                "id": row[0],
                "name": row[1],
                "level": row[2],
                "city": row[3],
                "group_name": row[4],
                "min_score": row[5],
                "min_rank": min_rank,
                "subject_requirement": row[7],
                "tuition": row[9],
                "is_sino_foreign": bool(row[10]),
                "source": row[11] or "2025录取数据",
                "confidence": row[12] or "MEDIUM",
                "tier": tier,
            }

            if major_cat not in major_groups:
                # Get major detail
                major_cursor = await db.execute(
                    """SELECT avg_salary_5yr, employment_rate, career_path, zhang_xuefeng_comment
                       FROM majors WHERE category = ? OR name LIKE ? LIMIT 1""",
                    (major_cat, f"%{major_cat}%")
                )
                major_row = await major_cursor.fetchone()

                major_groups[major_cat] = {
                    "major_category": major_cat,
                    "quality_score": q_score,
                    "civil_service_note": civil_note,
                    "growth_note": growth_note,
                    "avg_salary": major_row[0] if major_row else None,
                    "employment_rate": major_row[1] if major_row else None,
                    "career_path": major_row[2] if major_row else None,
                    "zhang_xuefeng_comment": major_row[3] if major_row else None,
                    "schools": [],
                }

            major_groups[major_cat]["schools"].append(school_info)

        # Phase 2: Sort by quality_score descending, then by number of schools
        results = sorted(
            major_groups.values(),
            key=lambda g: (g["quality_score"], len(g["schools"])),
            reverse=True
        )

        # Limit to top N unique majors
        return results[:max_results]
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
