"""Recommendation API v3 — AI-driven: DeepSeek decides what to recommend."""
import os, json, httpx
from fastapi import APIRouter
from app.models import RecommendV2Request, RecommendV2Response, MajorGroup, SchoolInfo
from app.engine import estimate_rank, match_majors, get_cutoff_scores

router = APIRouter()

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


async def ai_driven_recommend(
    score: int, rank: int, province: str, category: str, subject: str,
    candidates: list
) -> tuple[list[str], str]:
    """Let DeepSeek decide which majors to recommend and why."""

    # Build candidate summary
    lines = []
    for i, m in enumerate(candidates[:15]):
        schools_str = "、".join(
            f"{s['name']}({s['min_score']}分/{'冲刺' if s.get('tier')=='冲刺' else '稳妥' if s.get('tier')=='稳妥' else '保底'})"
            for s in m['schools'][:3]
        )
        emp = f"就业率{int(m['employment_rate']*100)}%" if m.get('employment_rate') else ""
        sal = f"年薪{m['avg_salary']/10000:.0f}万" if m.get('avg_salary') else ""
        lines.append(
            f"{i+1}. {m['major_category']}（质量{m['quality_score']}分）"
            f"{' | '+emp if emp else ''}{' | '+sal if sal else ''}"
            f" | 学校: {schools_str}"
        )

    prompt = f"""你是一位资深高考志愿规划师。一个{province}{category}考生，{score}分（全省位次{rank}名），选科{subject}。

以下是系统筛选出的所有候选专业方向：
{chr(10).join(lines)}

请你以「对孩子未来负责」的态度，从这些候选中选出最值得推荐的5个方向。你的标准是：
1. 就业确定性高 —— 毕业后真能找到好工作
2. 考公有优势 —— 如果孩子想考公务员
3. 薪资天花板 —— 5年10年后能拿多少
4. 长期价值 —— 35岁后还有竞争力吗
5. 分数匹配 —— 冲得上、稳得住、保得了

请用以下JSON格式返回（只返回JSON，不要其他文字）：
{{"recommendations": [
  {{"major": "专业名", "rank": 1, "score": 95, "reason": "为什么推荐这个方向（80字内）", "best_school": "最推荐的学校名", "risk": "有什么风险要注意（30字内）"}}
], "summary": "给家长的一句话总结（50字内）"}}

重要：只返回JSON，不要markdown代码块，不要解释。"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是高考志愿规划师。只返回合法JSON，不要任何其他文字。你的推荐直接影响孩子一生，必须认真负责。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            # Clean possible markdown wrappers
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            result = json.loads(text)
            recs = result.get("recommendations", [])
            summary = result.get("summary", "")
            return recs, summary
    except Exception as e:
        print(f"[v3 AI] Error: {e}")
        return [], None


@router.post("/recommend-v3", response_model=RecommendV2Response)
async def recommend_v3(req: RecommendV2Request):
    """AI-driven recommendation — DeepSeek decides what to recommend."""
    rank = await estimate_rank(req.province, req.score, req.category)
    cutoffs = await get_cutoff_scores(req.province, 2026, req.category)
    batch_cutoff = cutoffs.get("本科批")

    # Get broad candidates (lower quality threshold, more options for AI)
    candidates = await match_majors(
        province=req.province, category=req.category,
        subject_combo=req.subject_combo, estimated_rank=rank or 999999,
        min_quality_score=60, max_results=15,
    )

    # AI decides what to recommend
    ai_recs, ai_summary = await ai_driven_recommend(
        score=req.score, rank=rank or 0, province=req.province,
        category=req.category, subject=req.subject_combo,
        candidates=candidates,
    )

    # Map AI picks back to candidate data
    majors = []
    if ai_recs:
        for rec in ai_recs:
            # Find matching candidate
            matched = None
            for c in candidates:
                if rec["major"] in c["major_category"] or c["major_category"] in rec["major"]:
                    matched = c
                    break
            if not matched:
                matched = candidates[0] if candidates else None

            if matched:
                schools = [
                    SchoolInfo(
                        id=s["id"], name=s["name"], level=s["level"],
                        city=s["city"], min_score=s["min_score"],
                        min_rank=s["min_rank"], tier=s.get("tier", "稳妥"),
                        confidence=s.get("confidence", "MEDIUM"),
                    )
                    for s in matched["schools"]
                ]
                majors.append(MajorGroup(
                    major_category=rec["major"],
                    quality_score=rec.get("score", matched["quality_score"]),
                    civil_service_note=matched.get("civil_service_note", ""),
                    growth_note=rec.get("reason", ""),
                    avg_salary=matched.get("avg_salary"),
                    employment_rate=matched.get("employment_rate"),
                    career_path=matched.get("career_path"),
                    zhang_xuefeng_comment=(
                        f'AI推荐理由：{rec.get("reason","")} | '
                        f'推荐学校：{rec.get("best_school","")} | '
                        f'风险：{rec.get("risk","")}'
                    ),
                    schools=schools,
                ))

    # Fallback: if AI failed, use formula results
    if not majors:
        for m in candidates[:5]:
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

    return RecommendV2Response(
        province=req.province, score=req.score, category=req.category,
        estimated_rank=rank, cutoff_score=batch_cutoff,
        majors=majors,
        ai_summary=ai_summary or (ai_recs and "AI 深度分析完成" or None),
    )
