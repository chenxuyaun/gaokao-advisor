"""AI-powered features: admission probability, major comparison, career path planning."""
import os, json, httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List
from app.searcher import search_market

router = APIRouter(prefix="/api/ai", tags=["ai_features"])

# Load DeepSeek key
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
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


async def call_deepseek(prompt: str, system: str = "", max_tokens: int = 1000) -> Optional[str]:
    """Call DeepSeek API and return text response."""
    if not DEEPSEEK_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system or "你是有经验的高考志愿顾问。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[AI features] Error: {e}")
        return None


# ===== 1. 录取概率估算 =====

class ProbabilityRequest(BaseModel):
    province: str = "四川"
    score: int = 591
    category: str = "物理类"
    subject_combo: str = "物化生"
    university: str = ""
    major: str = ""

@router.post("/probability")
async def admission_probability(req: ProbabilityRequest):
    """Estimate admission probability for a specific university + major."""
    # Search for latest cutoff data
    search_data = await search_market([f"{req.university} {req.province} 录取分数线 2025"], limit=2)
    
    # 数据库查询真实录取数据
    db_ref = ""
    try:
        from app.database import get_db as db_get
        db = await db_get()
        cur = await db.execute("""
            SELECT u.name, ar.min_score, ar.min_rank, ar.major_category
            FROM admission_records ar JOIN universities u ON ar.university_id = u.id
            WHERE ar.target_province = ? AND ar.category = ? AND ar.year = 2025
              AND u.name LIKE ? ORDER BY ar.min_rank ASC LIMIT 5
        """, [req.province, req.category, f"%{req.university}%"])
        rows = await cur.fetchall()
        if rows:
            refs = [f"{r[0]}：{r[2]}名/{r[1]}分（{r[3]}）" for r in rows]
            db_ref = "【数据库中该院校在该省的真实录取数据】\n" + "\n".join(refs)
        await db.close()
    except:
        pass
    
    prompt = f"""你是高考志愿录取分析专家。请估算以下考生被特定院校+专业录取的概率。

考生信息：
- 省份：{req.province}，{req.category}，{req.score}分
- 选科：{req.subject_combo}
- 目标院校：{req.university}
- 目标专业：{req.major}

{db_ref}
搜索到的参考数据：
{search_data if search_data else "（无实时数据，请基于你的知识回答）"}

请从以下维度分析：
1. 录取概率（百分比，如85%）
2. 冲刺/稳妥/保底判定
3. 关键影响因素（分数线趋势、选科要求、招生计划变化等）
4. 备选建议（如果这个不稳，推荐什么替代）

返回JSON格式：
{{
  "probability": 85,
  "tier": "稳妥",
  "analysis": "分析文字（100字内）",
  "key_factors": ["因素1", "因素2", "因素3"],
  "backup": "备选建议（60字内）"
}}"""

    text = await call_deepseek(prompt, "你是录取分析专家。只返回JSON。", max_tokens=1000)
    if text:
        # Clean markdown wrappers
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text)
        except:
            pass
    return {"probability": 50, "tier": "数据不足", "analysis": "暂无法准确估算，建议查阅该院校往年录取数据。", "key_factors": [], "backup": ""}


# ===== 2. 专业对比 =====

class CompareRequest(BaseModel):
    majors: List[str] = ["计算机科学与技术", "临床医学"]
    province: str = "四川"
    category: str = "物理类"
    score: int = 591

@router.post("/compare")
async def compare_majors(req: CompareRequest):
    """Compare 2-3 majors across key dimensions."""
    search_data = await search_market([f"{m} 就业 2026" for m in req.majors[:3]], limit=3)
    
    # 数据库查询这些专业的相关学校录取数据
    db_ref = ""
    try:
        from app.database import get_db as db_get
        db = await db_get()
        for m in req.majors[:3]:
            cur = await db.execute("""
                SELECT u.name, ar.min_score, ar.min_rank, ar.target_province
                FROM admission_records ar JOIN universities u ON ar.university_id = u.id
                WHERE ar.major_category LIKE ? AND ar.target_province = ? AND ar.year = 2025
                ORDER BY ar.min_rank ASC LIMIT 3
            """, [f"%{m}%", req.province])
            rows = await cur.fetchall()
            if rows:
                refs = [f"{r[0]}({r[1]}分/{r[2]}名)" for r in rows]
                db_ref += f"  {m}在{req.province}的录取数据：{'、'.join(refs)}\n"
        await db.close()
    except:
        pass
    
    prompt = f"""你是高考志愿分析专家。请对比以下专业，从多个维度给出客观分析。

省份：{req.province} {req.category}，{req.score}分
对比专业：{"、".join(req.majors)}

{db_ref}
搜索到的参考数据：
{search_data if search_data else "（无实时数据，请基于你的知识回答）"}

请从以下维度对比（用具体数据）：
1. 薪资中位数（5年/10年）
2. 就业率
3. 技术壁垒/不可替代性
4. 35岁后竞争力
5. 考公优势
6. 学习难度
7. 适合性格类型

返回JSON格式：
{{
  "dimensions": ["薪资前景", "就业率", "技术壁垒", "长期价值", "考公优势", "学习难度"],
  "majors": [
    {{"name": "专业名", "scores": [85, 90, 95, 80, 30, 70], "summary": "一句话总结（30字）"}}
  ],
  "recommendation": "综合推荐（80字内）"
}}
每个维度分数0-100。"""

    text = await call_deepseek(prompt, "你是专业对比专家。只返回合法JSON。", max_tokens=1500)
    if text:
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text)
        except:
            pass
    return {"dimensions": [], "majors": [], "recommendation": "暂无法生成对比数据。"}


# ===== 3. 职业路径规划 =====

class PathRequest(BaseModel):
    major: str = "计算机科学与技术"
    province: str = "四川"
    score: int = 591
    category: str = "物理类"

@router.post("/career-path")
async def career_path(req: PathRequest):
    """Generate a multi-year career path plan for a chosen major."""
    search_data = await search_market([f"{req.major} 职业发展 2026", req.major + " 考研 就业"], limit=2)
    
    prompt = f"""你是职业规划专家。请为一个选择{req.major}专业的学生生成完整的职业发展路径规划。

学生信息：
- 省份：{req.province} {req.category}，{req.score}分
- 选择专业：{req.major}

搜索到的参考数据：
{search_data if search_data else "（无实时数据，请基于你的知识回答）"}

请规划以下四条路径（每条路径给出关键节点和时间线）：
1. 【就业路线】本科毕业直接就业 → 目标公司类型 → 薪资成长曲线 → 5年/10年发展
2. 【考研路线】考研目标院校 → 研究方向 → 毕业后就业方向 → 薪资对比
3. 【考公路线】可报考岗位 → 考试准备 → 职业发展 → 薪资稳定性
4. 【创业/自由路线】适合场景 → 准备工作 → 风险提示

返回JSON格式：
{{
  "paths": [
    {{
      "name": "就业路线",
      "timeline": [
        {{"year": "2026-2030", "title": "本科阶段", "content": "具体规划（40字内）"}},
        {{"year": "2030-2032", "title": "起步期", "content": "具体规划"}},
        {{"year": "2032-2036", "title": "发展期", "content": "具体规划"}}
      ],
      "pros": ["优势1", "优势2"],
      "cons": ["风险1", "风险2"]
    }}
  ],
  "summary": "给学生的建议（80字内）"
}}"""

    text = await call_deepseek(prompt, "你是职业规划专家。只返回合法JSON。", max_tokens=2000)
    if text:
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text)
        except:
            pass
    return {"paths": [], "summary": "暂无法生成路径规划。"}
