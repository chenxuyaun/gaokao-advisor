"""Recommendation API router (legacy v1 — delegates to v2 engine)."""
from fastapi import APIRouter
from app.models import RecommendRequest, RecommendResponse, UniversityInfo
from app.engine import estimate_rank, get_cutoff_scores

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    """Legacy endpoint — uses new engine, returns old format."""
    rank = await estimate_rank(req.province, req.score, req.category)

    cutoffs = await get_cutoff_scores(req.province, 2026, req.category)
    batch_cutoff = cutoffs.get("本科批")
    special_cutoff = cutoffs.get("特殊类型招生录取控制分数线") or cutoffs.get("特殊类型")
    cutoff_for_tips = special_cutoff or batch_cutoff
    cutoff_label = "特控线" if special_cutoff else "本科线"

    matches = await match_majors(
        province=req.province,
        category=req.category,
        subject_combo=req.subject_combo,
        estimated_rank=rank or 999999,
        min_quality_score=0,  # Show all for legacy
        max_results=20,
    )

    # Flatten major groups into old university-centric format
    suggestions = []
    for mg in matches:
        tier = mg["schools"][0]["tier"] if mg["schools"] else "保底"
        for s in mg["schools"]:
            suggestions.append(UniversityInfo(
                id=s["id"], name=s["name"], level=s["level"],
                city=s["city"], group_name=s.get("group_name"),
                min_score=s["min_score"], min_rank=s["min_rank"],
                subject_requirement=s.get("subject_requirement"),
                major_category=mg["major_category"],
                tuition=s.get("tuition"), is_sino_foreign=s.get("is_sino_foreign", False),
                source=s.get("source"), confidence=s.get("confidence"),
                notes=None, avg_salary=mg.get("avg_salary"),
                employment_rate=mg.get("employment_rate"),
                career_path=mg.get("career_path"),
                zhang_xuefeng_comment=mg.get("zhang_xuefeng_comment"),
                tier=tier,
            ))

    tips = None
    if rank:
        rush = [s for s in suggestions if s.tier == "冲刺"]
        steady = [s for s in suggestions if s.tier == "稳妥"]
        safe = [s for s in suggestions if s.tier == "保底"]
        over_cutoff = req.score - cutoff_for_tips
        tips = (
            f"你的位次约全省第{rank}名，超过{req.category}{cutoff_label}{cutoff_for_tips}分{over_cutoff}分。"
            f"共匹配到{len(suggestions)}个院校专业组："
            f"🔴冲刺{len(rush)}个 | 🟡稳妥{len(steady)}个 | 🟢保底{len(safe)}个。"
        )

    return RecommendResponse(
        province=req.province, score=req.score, category=req.category,
        estimated_rank=rank, cutoff_score=batch_cutoff,
        special_cutoff=special_cutoff, suggestions=suggestions, tips=tips,
    )
