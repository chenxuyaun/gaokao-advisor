"""Q&A and search-augmented analysis for parents."""
import os, json, httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from app import knowledge as kb

router = APIRouter()

# Config
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8888")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

# Load .env
ENV_PATH = os.path.expandvars(r"${HOME}\AppData\Local\hermes\.env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v


class AskRequest(BaseModel):
    province: str = "四川"
    score: int
    category: str = "物理类"
    subject_combo: str = "物化生"
    major: str  # e.g. "临床医学 / 口腔医学"
    school_name: Optional[str] = None  # specific school, or None for major-level
    questions: List[str]  # list of questions from parent


class AskAnswer(BaseModel):
    question: str
    answer: str
    sources: Optional[List[str]] = None


# ===== Dynamic question generation =====

@router.get("/ask/dynamic-questions")
async def dynamic_questions(province: str = "四川", category: str = "物理类", score: int = 500, major: str = ""):
    """Generate personalized questions based on student profile and recommended major."""
    if not DEEPSEEK_KEY:
        return {"questions": PARENT_QUESTIONS}
    
    major_context = f"该生考虑报考{major}专业。" if major else ""
    
    prompt = f"""你是一位高考志愿顾问。一个{province}{category}考生，{score}分。{major_context}
请根据该生的情况，生成3-5个家长最可能问的针对性问题。
要求：
- 问题具体、有针对性，不要笼统
- 结合该省份的就业特点和分数段
- 如果指定了专业，问题要围绕该专业展开
- 每个问题控制在20字以内

返回格式：只返回JSON数组，如["问题1", "问题2", "问题3"]"""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是高考志愿顾问。只返回JSON数组，不要其他文字。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            questions = json.loads(text)
            if isinstance(questions, list) and len(questions) >= 3:
                return {"questions": questions}
    except Exception as e:
        print(f"[AI questions] Error: {e}")
    
    return {"questions": PARENT_QUESTIONS}  # search result URLs


class AskResponse(BaseModel):
    major: str
    school: Optional[str] = None
    answers: List[AskAnswer]


async def search_web(query: str, limit: int = 3) -> list:
    """Search web FREE — Wikipedia + 360 + DuckDuckGo, zero cost."""

    all_results = []

    # 1. Wikipedia (education topics)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://zh.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": str(limit)},
                headers={"User-Agent": "GaokaoAdvisor/2.0"},
            )
            data = resp.json()
            for r in data.get("query", {}).get("search", [])[:limit]:
                all_results.append({
                    "title": r.get("title", ""),
                    "url": f"https://zh.wikipedia.org/wiki/{r['title'].replace(' ','_')}",
                    "snippet": r.get("snippet", "")[:300].replace('<span class="searchmatch">','').replace('</span>',''),
                    "engine": "wikipedia",
                })
    except Exception:
        pass

    # 2. 360 Search (so.com) — best Chinese search, free
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.so.com/s",
                params={"q": query, "pn": "1"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            )
            text = resp.text
            import re
            links = re.findall(r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.DOTALL)
            for i, (url, title) in enumerate(links[:limit]):
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                if title_clean and url.startswith("http"):
                    all_results.append({
                        "title": title_clean,
                        "url": url,
                        "snippet": query,  # 360 doesn't expose snippets in HTML easily
                        "engine": "360search",
                    })
    except Exception:
        pass

    # 3. DuckDuckGo HTML
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            import re
            links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>', resp.text)
            snippets = re.findall(r'<a class="result__snippet"[^>]*>([^<]+)</a>', resp.text)
            for i, (url, title) in enumerate(links[:limit]):
                snippet = snippets[i] if i < len(snippets) else ""
                all_results.append({"title": title, "url": url, "snippet": snippet[:300], "engine": "duckduckgo"})
    except Exception:
        pass

    # Deduplicate by URL, return top N
    seen = set()
    results = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            results.append({"title": r["title"], "url": r["url"], "snippet": r.get("snippet", "")})
        if len(results) >= limit:
            break

    return results


# Pre-built parent question templates with answer hints
QUESTION_HINTS = {
    "这个专业出来做什么工作？": "请具体列出3-5个典型工作岗位，以及工作内容简述。",
    "毕业后好找工作吗？薪资多少？": "请给出就业率数据和起薪范围，区分本科和研究生。",
    "能考公务员吗？什么岗位？": "请列出具体可报考的公务员/事业编岗位名称。",
    "这个专业未来10年会贬值吗？": "请分析行业趋势，哪些方向在增长，哪些在萎缩。",
    "适合女生/男生读吗？": "请从工作环境、体力要求、行业性别比例等角度客观分析。",
    "学费贵不贵？有没有隐形费用？": "请说明学费范围，以及是否需要额外考证/培训费用。",
    "这个学校和同档次的比怎么样？": "请横向对比同分数段的其他学校，说优势劣势。",
    "学风怎么样？老师负责任吗？": "请基于公开信息和学生评价，客观描述。",
    "宿舍条件好吗？食堂怎么样？": "请搜索学校的具体生活条件信息。",
    "毕业后能留在大城市吗？": "请分析该专业在一线/新一线城市的就业机会。",
    "需要考研吗？不考研能找到工作吗？": "请分析该专业本科vs研究生的就业差距。",
    "这个专业毕业能拿多少钱？5年后呢？": "请给出起薪和5年经验的薪资区间。",
}


@router.post("/ask", response_model=AskResponse)
async def ask_parent_questions(req: AskRequest):
    """Parents ask questions about a major/school — AI answers with web search augmentation."""
    context = f"考生：{req.province} {req.category} {req.subject_combo}，{req.score}分。\n"
    context += f"专业方向：{req.major}。\n"
    if req.school_name:
        context += f"目标学校：{req.school_name}。\n"

    # Search for latest info
    search_query = f"{req.major} {' '.join(req.questions[:2])} 2025 2026"
    if req.school_name:
        search_query = f"{req.school_name} {req.major} 就业 录取"
    
    search_results = await search_web(search_query)
    search_text = ""
    sources = []
    if search_results:
        for s in search_results:
            search_text += f"- {s['title']}: {s['snippet'][:200]}\n"
            sources.append(s["url"])
    
    # 数据库查询真实录取数据，防止AI编造
    db_context = ""
    try:
        from app.database import get_db
        db = await get_db()
        # 查该学校+专业的录取数据
        cur = await db.execute("""
            SELECT u.name, ar.min_score, ar.min_rank, ar.target_province, ar.year
            FROM admission_records ar JOIN universities u ON ar.university_id = u.id
            WHERE u.name LIKE ? AND ar.major_category LIKE ?
            ORDER BY ar.year DESC LIMIT 3
        """, [f"%{req.school_name or ''}%", f"%{req.major or ''}%"])
        rows = await cur.fetchall()
        if rows:
            refs = []
            for r in rows:
                refs.append(f"{r[0]}在{r[3]}{r[4]}年录取{r[1]}分/{r[2]}名")
            db_context = "【数据库中的真实录取数据】\n" + "\n".join(refs) + "\n"
        await db.close()
    except:
        pass

    # Build answers for each question
    answers = []
    for question in req.questions:
        hint = QUESTION_HINTS.get(question, "")

        # Check knowledge base first
        cached = kb.lookup(question, req.major, req.school_name)
        if cached:
            answers.append(AskAnswer(
                question=question,
                answer=cached["answer"],
                sources=cached.get("sources"),
            ))
            continue
        
        search_block = "以下是最新的网络搜索结果供参考：\n" + search_text if search_text else "（无实时搜索结果，请基于你的知识回答）"
        db_block = f"\n{db_context}\n" if db_context else ""
        
        prompt = f"""你是一位资深高考志愿顾问，正在帮助一位四川家长解答孩子的高考志愿问题。

{context}

家长的问题是：「{question}」
{hint}

{search_block}
{db_block}

请用150字以内，用口语化的中文回答。要求：
1. 说人话，像一个懂行的亲戚在聊天
2. 有具体数据就说数据，没有就说"建议查一下最新数据"
3. 不要编造数据
4. 如果信息不确定，明确说这方面建议你自己再核实一下 """

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    DEEPSEEK_URL,
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "你是高考志愿顾问+职业规划师。用口语化中文回答，直接、诚实、接地气。"},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 300,
                        "temperature": 0.5,
                    },
                )
                data = resp.json()
                answer = data["choices"][0]["message"]["content"].strip()
                # Store to knowledge base
                kb.store(
                    question=question,
                    major=req.major,
                    answer=answer,
                    school=req.school_name,
                    sources=sources[:3] if sources else None,
                    search_snippet=search_text[:500] if search_text else None,
                )
        except Exception as e:
            answer = f"抱歉，AI分析暂时不可用（{str(e)[:50]}）。建议直接搜索相关学校官网了解详情。"

        answers.append(AskAnswer(
            question=question,
            answer=answer,
            sources=sources[:3] if sources else None,
        ))

    return AskResponse(
        major=req.major,
        school=req.school_name,
        answers=answers,
    )


@router.get("/ask/questions")
async def get_question_templates():
    """Return pre-built parent question templates."""
    return {
        "questions": [
            {"id": q, "text": q, "icon": "💼" if "工作" in q else "💰" if "薪资" in q or "钱" in q else "🏛️" if "公务员" in q or "考公" in q else "📈" if "未来" in q or "贬值" in q else "👤" if "女生" in q or "男生" in q else "💸" if "学费" in q else "🏫" if "学校" in q or "学风" in q else "🏠" if "宿舍" in q or "食堂" in q else "🏙️" if "大城市" in q else "🎓" if "考研" in q else "❓"}
            for q in QUESTION_HINTS.keys()
        ]
    }


@router.get("/knowledge/stats")
async def knowledge_stats():
    """Return knowledge base statistics."""
    return kb.stats()
