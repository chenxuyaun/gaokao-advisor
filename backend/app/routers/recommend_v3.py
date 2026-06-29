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

    # ===== 实时市场数据搜索（三引擎） =====
    market_section = ""
    try:
        search_queries = []
        for m in candidates[:4]:
            cat = m['major_category'].split("/")[0].split(" ")[0]
            if len(cat) >= 2:
                search_queries.append(f"{cat} 2026 就业")
        from app.searcher import search_market
        market_data = await search_market(search_queries)
        if market_data:
            market_section = f"\n【2026年最新市场数据】\n以下是实时搜索到的相关专业就业市场信息（请优先使用这些数据）：\n{market_data}\n"
    except:
        pass

    prompt = f"""你是一位资深高考志愿规划师，你分析问题的风格像张雪峰老师：数据驱动、就业导向、对普通家庭负责。

考生信息：
- 省份：{province} {category}，{score}分（全省位次{rank}名），选科{subject}

以下是系统筛选出的所有候选专业方向（含就业率、薪资、学校）：
{chr(10).join(lines)}
{market_section}
请用「张雪峰式」的思维做推荐——你的核心方法论：
1. 【就业倒推法】从就业数据倒推选择——看中位数毕业生的去向，不看顶尖案例
2. 【阶层现实主义】默认孩子是普通家庭——先谋生再谋爱，先站稳再登高
3. 【不可替代性检验】优先选有技术壁垒的专业
4. 【500强测试】看哪些学校哪些专业真能进好企业
5. 【家庭背景分流】当专业选择涉及人脉/资源门槛时，要提醒

请用以下JSON格式返回（只返回JSON，不要其他文字）：
{{"recommendations": [
  {{"major": "专业名", "rank": 1, "score": 95, "reason": "为什么推荐（80字内，数据驱动，直接说人话）", "best_school": "最推荐的学校名", "risk": "有什么风险要注意（30字内）"}}
], "summary": "给家长的一句话总结（50字内，像张雪峰那样一针见血）"}}

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

    # Fallback: if AI returned fewer than 5, supplement with formula results
    if len(majors) < 5:
        existing = {m.major_category for m in majors}
        for m in candidates[:10]:
            if m["major_category"] in existing:
                continue
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
            if len(majors) >= 5:
                break

    return RecommendV2Response(
        province=req.province, score=req.score, category=req.category,
        estimated_rank=rank, cutoff_score=batch_cutoff,
        majors=majors,
        ai_summary=ai_summary or (ai_recs and "AI 深度分析完成" or None),
    )
