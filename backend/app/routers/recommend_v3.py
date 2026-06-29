"""Recommendation API v3 — AI-driven: DeepSeek does matching, scoring, and analysis."""
import os, json, httpx
from fastapi import APIRouter
from app.models import RecommendV2Request, RecommendV2Response, MajorGroup, SchoolInfo
from app.engine import estimate_rank, get_cutoff_scores
from app.searcher import search_market

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

# Province tier data (minimal reference for AI, ~total students per category)
PROVINCE_REF = {
    "广东": "80万考生,物理类约35万",
    "河南": "130万考生,物理类约42万",
    "山东": "100万考生,综合类约45万",
    "四川": "77万考生,物理类约30万",
    "江苏": "40万考生,物理类约28万",
    "河北": "60万考生,物理类约32万",
    "湖南": "50万考生,物理类约30万",
    "安徽": "50万考生,物理类约25万",
    "湖北": "46万考生,物理类约22万",
    "浙江": "36万考生,综合类约29万",
    "北京": "5万考生,综合类",
    "上海": "5万考生,综合类",
    "天津": "7万考生,综合类",
    "重庆": "20万考生,物理类约11万",
    "福建": "20万考生,物理类约18万",
    "江西": "40万考生,物理类约20万",
    "陕西": "30万考生,物理类约15万",
    "辽宁": "20万考生,物理类约13万",
    "云南": "38万考生,物理类约18万",
    "贵州": "40万考生,物理类约22万",
    "山西": "30万考生,物理类约16万",
    "黑龙江": "18万考生,物理类约11万",
    "吉林": "15万考生,物理类约9万",
    "甘肃": "20万考生,物理类约12万",
    "广西": "40万考生,物理类约20万",
    "内蒙古": "16万考生,物理类约8万",
    "新疆": "15万考生,物理类约8万",
    "海南": "5万考生,综合类",
    "宁夏": "7万考生,物理类约5万",
    "青海": "4万考生,物理类约3万",
    "西藏": "2万考生,物理类约2万",
}

# 985/211/双一流 list for AI reference (so it doesn't have to guess)
TOP_UNIS = {
    "985": "北京大学,清华大学,复旦大学,上海交通大学,浙江大学,南京大学,中国科学技术大学,中国人民大学,哈尔滨工业大学,西安交通大学,武汉大学,华中科技大学,中山大学,北京航空航天大学,北京理工大学,同济大学,南开大学,天津大学,东南大学,厦门大学,电子科技大学,四川大学,华南理工大学,重庆大学,兰州大学,北京师范大学,华东师范大学,湖南大学,中南大学,大连理工大学,东北大学,吉林大学,山东大学,中国海洋大学,西北农林科技大学,中国农业大学,中央民族大学,国防科技大学",
    "211": "北京科技大学,北京交通大学,北京邮电大学,北京化工大学,北京工业大学,北京林业大学,北京外国语大学,北京体育大学,北京中医药大学,华北电力大学,中国矿业大学(北京),中国石油大学(北京),中国地质大学(北京),中央财经大学,对外经济贸易大学,中国政法大学,首都师范大学,南京航空航天大学,南京理工大学,南京师范大学,中国矿业大学,河海大学,江南大学,南京农业大学,中国药科大学,苏州大学,上海财经大学,上海大学,华东理工大学,东华大学,上海外国语大学,上海中医药大学,西南交通大学,西南财经大学,四川农业大学,郑州大学,南昌大学,福州大学,合肥工业大学,安徽大学,武汉理工大学,华中农业大学,华中师范大学,中南财经政法大学,中国地质大学(武汉),湖南师范大学,华南师范大学,暨南大学,西安电子科技大学,陕西师范大学,长安大学,西北大学,河北工业大学,太原理工大学,云南大学,广西大学,贵州大学,海南大学,内蒙古大学,宁夏大学,青海大学,西藏大学,石河子大学,新疆大学,延边大学,辽宁大学,大连海事大学,东北林业大学,东北农业大学,哈尔滨工程大学",
}

CONFIDENCE = "MEDIUM"

@router.post("/recommend-v3", response_model=RecommendV2Response)
async def recommend_v3(req: RecommendV2Request):
    """AI-driven recommendation — DeepSeek does matching, scoring, and analysis with real-time search."""
    rank = await estimate_rank(req.province, req.score, req.category)
    cutoffs = await get_cutoff_scores(req.province, 2026, req.category)
    batch_cutoff = cutoffs.get("本科批")

    # Build cutoff info for prompt
    special_cutoff = cutoffs.get("特殊类型招生录取控制分数线")
    cutoff_line = f"特控线{special_cutoff}分" if special_cutoff else ""
    batch_line = f"本科线{batch_cutoff}分" if batch_cutoff else ""

    province_ref = PROVINCE_REF.get(req.province, "")

    # === Real-time market search ===
    market_section = ""
    try:
        search_queries = [
            f"{req.province} 2025 高考 录取分数线",
            "2026 应届生 就业 薪资 中位数",
        ]
        market_data = await search_market(search_queries)
        if market_data:
            market_section = f"\n【实时市场数据参考】\n{market_data}\n"
    except:
        pass
    
    province_ref = PROVINCE_REF.get(req.province, "")

    # === 数据库查询真实匹配的学校 ===
    db_matches = ""
    try:
        from app.database import get_db as db_get
        db = await db_get()
        lo, hi = int(rank * 0.7), int(rank * 1.5)
        cur = await db.execute("""
            SELECT u.name, u.level, ar.min_score, ar.min_rank, ar.major_category
            FROM admission_records ar JOIN universities u ON ar.university_id = u.id
            WHERE ar.target_province = ? AND ar.category = ? AND ar.year = 2025
              AND ar.min_rank BETWEEN ? AND ?
            ORDER BY ar.min_rank ASC LIMIT 30
        """, [req.province, req.category, lo, hi])
        rows = await cur.fetchall()
        if rows:
            grouped = {}
            for r in rows:
                cat = r[4] or "综合类"
                if cat not in grouped:
                    grouped[cat] = []
                grouped[cat].append(f"{r[0]}({r[2]}分/{r[3]}名)")
            parts = []
            for cat, schools in sorted(grouped.items(), key=lambda x: -len(x[1]))[:10]:
                parts.append(f"  {cat}: {'、'.join(schools[:3])}")
            db_matches = "【数据库中该位次附近的真实录取数据】\n" + "\n".join(parts)
        await db.close()
    except:
        pass

    prompt = f"""你是高考志愿顾问+张雪峰风格分析。基于以下真实录取数据，为考生推荐最适合的专业方向。

【考生信息】
- 省份：{req.province}（{province_ref}）
- 分数：{req.score}分，全省位次：约{rank}名
- 类别：{req.category} | 选科：{req.subject_combo}
- 分数线：{cutoff_line}，{batch_line}

{db_matches}
{market_section}
【工作要求】
1. 基于该省2025年录取数据（位次），推荐5-8个适合该考生位次（约{rank}名）的专业方向
2. 每个专业方向列出1-3所具体大学，标注冲刺/稳妥/保底
3. 用张雪峰风格分析：就业导向、数据驱动、说人话
4. 默认考生是普通家庭，优先考虑就业确定性
5. 理科优先推荐有技术壁垒的专业，文科优先推荐考公/师范方向

请用以下JSON格式返回（只返回JSON）：
{{
  "recommendations": [
    {{"major": "专业名", "rank": 1, "score": 分数(0-100), "reason": "推荐理由（80字内，引用数据）", "best_school": "最推荐的学校", "best_school_score": 该校预估录取分, "best_school_tier": "冲刺/稳妥/保底", "risk": "风险提示（30字内）"}}
  ],
  "summary": "给家长的总结建议（100字内，张雪峰风格）"
}}"""

    majors = []
    ai_summary = None

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是高考志愿规划师+张雪峰。只返回合法JSON，不要任何其他文字。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            result = json.loads(text)
            recs = result.get("recommendations", [])
            ai_summary = result.get("summary", "")

            for rec in recs:
                # Estimate score from tier + cutoff
                tier = rec.get("best_school_tier", "稳妥")
                est_score = batch_cutoff if batch_cutoff else 400
                if tier == "冲刺":
                    est_score += 30
                elif tier == "保底":
                    est_score -= 20
                ai_score = rec.get("best_school_score")
                if ai_score and ai_score > 0:
                    est_score = ai_score
                
                # Look up school level/city from database
                school_info = {"level": "", "city": ""}
                school_name = rec.get("best_school", "")
                try:
                    from app.database import get_db as db_get2
                    db2 = await db_get2()
                    cur2 = await db2.execute("SELECT level, city FROM universities WHERE name LIKE ? LIMIT 1", [f"%{school_name}%"])
                    row2 = await cur2.fetchone()
                    if row2:
                        school_info = {"level": row2[0] or "", "city": row2[1] or ""}
                        print(f"[v3] School lookup: {school_name} -> {school_info}")
                    else:
                        print(f"[v3] School NOT found: {school_name}")
                    await db2.close()
                except Exception as e:
                    print(f"[v3] School lookup error: {e}")
                    pass
                
                majors.append(MajorGroup(
                    major_category=rec.get("major", "综合类"),
                    quality_score=rec.get("score", 70),
                    civil_service_note="",
                    growth_note=rec.get("reason", ""),
                    avg_salary=None,
                    employment_rate=None,
                    career_path="",
                    zhang_xuefeng_comment=(
                        f'AI推荐理由：{rec.get("reason","")} | '
                        f'推荐学校：{rec.get("best_school","")} | '
                        f'风险：{rec.get("risk","")}'
                    ),
                    schools=[
                        SchoolInfo(
                            id=0, name=rec.get("best_school", ""),
                            level=school_info.get("level",""), city=school_info.get("city",""),
                            min_score=est_score,
                            min_rank=0,
                            tier=rec.get("best_school_tier", "稳妥"), confidence=CONFIDENCE,
                        )
                    ] if rec.get("best_school") else [],
                ))
    except Exception as e:
        print(f"[v3 AI] Error: {e}")

    if not majors:
        # Ultimate fallback
        for i, (name, reason) in enumerate([
            ("计算机科学与技术", "就业率90%+，薪资高，技术壁垒强"),
            ("临床医学", "越老越值钱，就业确定性极高"),
            ("电气工程及其自动化", "进国家电网，稳定铁饭碗"),
            ("法学", "考公第一大专业，岗位多"),
            ("会计学", "考公+企业双方向，稳定"),
        ][:5]):
            majors.append(MajorGroup(
                major_category=name, quality_score=85 - i * 5,
                civil_service_note="", growth_note=reason,
                avg_salary=None, employment_rate=None, career_path="",
                zhang_xuefeng_comment=f"AI推荐理由：{reason} | 风险：需结合具体分数查询",
                schools=[],
            ))
        ai_summary = ai_summary or "建议结合具体分数和省排名，用实时搜索功能查询最新录取数据。"

    return RecommendV2Response(
        province=req.province, score=req.score, category=req.category,
        estimated_rank=rank, cutoff_score=batch_cutoff,
        majors=majors,
        ai_summary=ai_summary,
    )
