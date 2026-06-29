"""Recommendation API router."""
from fastapi import APIRouter
from app.models import RecommendRequest, RecommendResponse, UniversityInfo
from app.engine import estimate_rank, match_universities, get_cutoff_scores

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    """Core recommendation endpoint."""
    rank = await estimate_rank(req.province, req.score, req.category)

    cutoffs = await get_cutoff_scores(req.province, 2026, req.category)
    batch_cutoff = cutoffs.get("本科批")
    special_cutoff = cutoffs.get("特殊类型招生录取控制分数线") or cutoffs.get("特殊类型")
    cutoff_for_tips = special_cutoff or batch_cutoff
    cutoff_label = "特控线" if special_cutoff else "本科线"

    matches = await match_universities(
        province=req.province,
        category=req.category,
        subject_combo=req.subject_combo,
        estimated_rank=rank,
        prefer_city=req.prefer_city,
        prefer_major_category=req.prefer_major_category,
        max_tuition=req.max_tuition,
        rush_ratio=req.rush_ratio,
        safe_ratio=req.safe_ratio,
    )

    suggestions = [UniversityInfo(**m) for m in matches]

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
            f"建议重点考虑'稳妥'档，把'冲刺'档填在靠前志愿位置。"
        )

    return RecommendResponse(
        province=req.province,
        score=req.score,
        category=req.category,
        estimated_rank=rank,
        cutoff_score=batch_cutoff,
        special_cutoff=special_cutoff,
        suggestions=suggestions,
        tips=tips,
    )
