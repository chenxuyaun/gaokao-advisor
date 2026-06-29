"""Recommendation API v2 — major-first with responsible AI career analysis."""
import os
import json
import httpx
from fastapi import APIRouter
from app.models import (
    RecommendV2Request, RecommendV2Response,
    MajorGroup, SchoolInfo
)
from app.engine import estimate_rank, match_majors, get_cutoff_scores
from app.engine import MAJOR_QUALITY

router = APIRouter()

# Load secrets from Hermes .env
ENV_PATH = os.path.expandvars(r"${HOME}\AppData\Local\hermes\.env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")


def _normalize_major_group(major_cat: str) -> str:
    """Merge fragmented major categories into clean groups."""
    if "临床医" in major_cat or "口腔" in major_cat or "麻醉" in major_cat or "医学影像" in major_cat:
        return "临床医学 / 口腔医学"
    if "眼视光" in major_cat:
        return "临床医学 / 口腔医学"
    if "计算机" in major_cat or "信息" in major_cat or "软件" in major_cat or "通信" in major_cat or "数据" in major_cat:
        if "经管" in major_cat:
            return "经管 / 财经"
        return "计算机 / 电子信息"
    if "电气" in major_cat or "自动化" in major_cat:
        return "电气 / 自动化"
    if "法" in major_cat:
        return "法学"
    if "会计" in major_cat or "审计" in major_cat or "财经" in major_cat or "经管" in major_cat or "金融" in major_cat:
        return "经管 / 财经"
    if "材料" in major_cat:
        return "材料 / 化工"
    if "化学" in major_cat or "化工" in major_cat:
        return "材料 / 化工"
    if "地质" in major_cat or "环境" in major_cat or "核" in major_cat:
        return "环境 / 能源"
    if "生物" in major_cat:
        return "生物科学"
    if "师范" in major_cat:
        return "师范"
    return major_cat


async def generate_ai_analysis(score: int, rank: int, province: str, category: str, subject: str, majors: list) -> str:
    """Generate deeply responsible career analysis for the recommendation set.

    This is the most critical function in the system. Every word here can influence
    a student's life trajectory. Must be honest, practical, and grounded.
    """
    # Build major summary for the AI
    lines = []
    top_bonus = 0
    for i, m in enumerate(majors[:8]):
        cat = m['major_category']
        qs = m['quality_score']
        schools = m.get('schools', [])
        top_school = schools[0] if schools else None
        line = f"{i+1}. {cat}（质量{qs}分）"
        if top_school:
            line += f" — 如 {top_school['name']}"
        if m.get('employment_rate'):
            line += f"，就业率{int(m['employment_rate']*100)}%"
        if m.get('avg_salary'):
            line += f"，5年薪资{m['avg_salary']/10000:.0f}万"
        lines.append(line)

        # Score bonus tiers for strategy
        if 585 <= score <= 600 and qs >= 95:
            top_bonus += 1

    major_list = "\n".join(lines)

    # Determine student tier
    if rank <= 10000:
        tier_hint = "高分段（全省前1万名），985/211基本稳，可以优先考虑顶尖学校的王牌专业"
    elif rank <= 30000:
        tier_hint = "中高分段（全省前3万名），211稳、985边，建议优先专业>学校，选好专业比选好学校更重要"
    elif rank <= 80000:
        tier_hint = "中等分段，建议优先考虑就业确定性强、考公有优势的专业，不要盲目冲名校冷门专业"
    else:
        tier_hint = "建议以就业为导向，优先选有技术壁垒的实用专业"

    salary_5yr = ""
    for m in majors[:3]:
        if m.get('avg_salary'):
            salary_5yr = f"（参考：该方向5年平均薪资约{m['avg_salary']/10000:.0f}万/年）"
            break

    prompt = f"""你像张雪峰老师一样——数据驱动、就业导向、说人话、不给模糊建议。这是你的工作方式：

你现在是一个普通{province}{category}考生（{score}分，全省位次{rank}名，选科{subject}）的志愿顾问。

{tier_hint}

系统根据就业率、薪资、考公方向、行业前景等综合评分，推荐了以下专业方向：
{major_list}
{salary_5yr}

请你用张雪峰式的思维框架来回答（300字以内，东北大哥语气，说数据说判断，不说套话）：

1.【首选推荐】这些方向你最推荐哪2-3个？为什么？
   → 用就业倒推法：看中位数毕业生去向，不看顶尖案例
   → 用不可替代性检验：哪个专业有技术壁垒？

2.【避坑提醒】有没有看似不错但实际要小心的？
   → 用阶层现实主义：普通家庭的孩子进去能站稳吗？

3.【考公路线】如果孩子想考公务员，哪些专业有优势？
   → 给出具体岗位，别说「岗位很多」这种废话

4.【一句话总结】给家长一句话建议
   → 像张雪峰那样一针见血，适合转发那种

要求：先给判断再解释，别铺垫四段才说结论。引用具体数据。不模棱两可。
要求：
- 说真话，不要为了讨好而推荐不靠谱的方向
- 数据驱动，提到具体的学校和专业时标注数据来源的局限性
- 如果某些专业方向数据不足，明确指出
- 不要用AI腔调（如在当今时代、随着...的发展、综上所述）
- 像个过来人亲戚一样说话，接地气但有干货"""

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是一位资深高考志愿规划师+职业规划顾问，拥有20年经验。你用口语化的中文，给出直接、坦诚、有数据支撑的建议。你不说空话套话，对孩子的未来负责。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 600,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            print(f"[AI] DeepSeek error: {data.get('error', data)[:200]}")
            return None
    except Exception as e:
        print(f"[AI] Exception: {e}")
        return None


@router.post("/recommend-v2", response_model=RecommendV2Response)
async def recommend_v2(req: RecommendV2Request):
    """Major-first recommendation with AI career analysis."""
    print(f"[v2] Request: {req.province} {req.score}分 {req.category} {req.subject_combo}")

    rank = await estimate_rank(req.province, req.score, req.category)

    cutoffs = await get_cutoff_scores(req.province, 2026, req.category)
    batch_cutoff = cutoffs.get("本科批")

    matches = await match_majors(
        province=req.province,
        category=req.category,
        subject_combo=req.subject_combo,
        estimated_rank=rank or 999999,
        min_quality_score=70,
        max_results=15,
    )

    print(f"[v2] Raw matches: {len(matches)} groups")

    # Merge fragmented major groups
    merged: dict = {}
    for m in matches:
        norm = _normalize_major_group(m["major_category"])
        if norm not in merged:
            merged[norm] = {
                "major_category": norm,
                "quality_score": m["quality_score"],
                "civil_service_note": m["civil_service_note"],
                "growth_note": m["growth_note"],
                "avg_salary": m.get("avg_salary"),
                "employment_rate": m.get("employment_rate"),
                "career_path": m.get("career_path"),
                "zhang_xuefeng_comment": m.get("zhang_xuefeng_comment"),
                "schools": list(m["schools"]),
            }
        else:
            merged[norm]["schools"].extend(m["schools"])
            merged[norm]["quality_score"] = max(merged[norm]["quality_score"], m["quality_score"])
            # Take the best salary/employment data
            if m.get("avg_salary") and (not merged[norm].get("avg_salary") or m["avg_salary"] > merged[norm]["avg_salary"]):
                merged[norm]["avg_salary"] = m["avg_salary"]
            if m.get("employment_rate") and (not merged[norm].get("employment_rate") or m["employment_rate"] > merged[norm]["employment_rate"]):
                merged[norm]["employment_rate"] = m["employment_rate"]

    # Cap quality scores
    for v in merged.values():
        v["quality_score"] = min(v["quality_score"], 100)
        # Remove duplicate schools
        seen_ids = set()
        unique_schools = []
        for s in v["schools"]:
            if s["id"] not in seen_ids:
                seen_ids.add(s["id"])
                unique_schools.append(s)
        v["schools"] = sorted(unique_schools, key=lambda x: x["min_rank"] or 999999)

    # Sort by quality score
    sorted_majors = sorted(merged.values(), key=lambda x: x["quality_score"], reverse=True)[:8]

    # Build response
    majors = []
    for m in sorted_majors:
        schools = [
            SchoolInfo(
                id=s["id"], name=s["name"], level=s["level"],
                city=s["city"], min_score=s["min_score"],
                min_rank=s["min_rank"], tier=s.get("tier", "稳妥"),
                confidence=s.get("confidence", "MEDIUM"),
            )
            for s in m["schools"]
        ]
        majors.append(MajorGroup(
            major_category=m["major_category"],
            quality_score=m["quality_score"],
            civil_service_note=m["civil_service_note"],
            growth_note=m["growth_note"],
            avg_salary=m.get("avg_salary"),
            employment_rate=m.get("employment_rate"),
            career_path=m.get("career_path"),
            zhang_xuefeng_comment=m.get("zhang_xuefeng_comment"),
            schools=schools,
        ))

    print(f"[v2] Merged majors: {len(majors)}")
    for m in majors:
        print(f"  {m.quality_score}分 {m.major_category} → {len(m.schools)}校")

    # AI Analysis
    ai_summary = await generate_ai_analysis(
        score=req.score, rank=rank or 0,
        province=req.province, category=req.category,
        subject=req.subject_combo, majors=matches,
    )
    print(f"[v2] AI summary: {'OK' if ai_summary else 'FAILED'} ({len(ai_summary) if ai_summary else 0} chars)")

    return RecommendV2Response(
        province=req.province,
        score=req.score,
        category=req.category,
        estimated_rank=rank,
        cutoff_score=batch_cutoff,
        majors=majors,
        ai_summary=ai_summary,
    )
