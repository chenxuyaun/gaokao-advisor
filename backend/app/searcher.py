"""Shared search module — free multi-engine search for real-time market data."""
import httpx, re

async def search_market(major_keywords: list[str], limit: int = 2) -> str:
    """Search latest market data for given majors across 3 free engines.
    Returns formatted string for prompt injection, or empty string."""
    all_results = []
    
    async with httpx.AsyncClient(timeout=8) as client:
        for keyword in major_keywords[:3]:
            # 1. Wikipedia
            try:
                resp = await client.get(
                    "https://zh.wikipedia.org/w/api.php",
                    params={"action":"query","list":"search","srsearch":keyword,"format":"json","srlimit":"1"},
                    headers={"User-Agent":"GaokaoAdvisor/2.0"},
                )
                data = resp.json()
                for r in data.get("query",{}).get("search",[])[:1]:
                    snippet = r.get("snippet","")[:200].replace('<span class="searchmatch">','').replace('</span>','')
                    all_results.append(f"[百科] {keyword}: {snippet}")
            except:
                pass
            
            # 2. 360 search
            try:
                resp = await client.get(
                    "https://www.so.com/s",
                    params={"q": keyword, "pn": "1"},
                    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )
                links = re.findall(r'<h3[^>]*class=\"[^\"]*res-title[^\"]*\"[^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                for i, (url, title) in enumerate(links[:1]):
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    if title_clean:
                        all_results.append(f"[360] {keyword}: {title_clean[:200]}")
            except:
                pass
            
            # 3. DuckDuckGo
            try:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": keyword},
                    headers={"User-Agent":"Mozilla/5.0"},
                )
                ddg = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|td)>', resp.text, re.DOTALL)
                for snippet in ddg[:1]:
                    clean = re.sub(r'<[^>]+>', '', snippet).strip()[:200]
                    if clean:
                        all_results.append(f"[资讯] {keyword}: {clean}")
            except:
                pass
    
    if not all_results:
        return ""
    
    return "\n".join(f"📊 {r}" for r in all_results[:6])
