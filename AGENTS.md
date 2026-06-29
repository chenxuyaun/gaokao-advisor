# Gaokao Advisor — AGENTS.md

Python 3.9+ | FastAPI + SQLite + 纯HTML前端 | 端口 8083

## 项目结构
```
D:\gaokao-advisor\
├── backend/app/          # FastAPI (main.py, database.py, engine.py, models.py, routers/)
├── frontend/index.html   # Notion 风格单页应用
├── data/                 # gaokao.db + seed_sichuan.py
├── Dockerfile, docker-compose.yml, nginx.conf
```

## 命令
- 后端: `uvicorn app.main:app --host 0.0.0.0 --port 8083` (在 backend 目录)
- 种子: `python data/seed_sichuan.py` (在项目根目录)
- 验证: `python -c "from app.engine import match_universities; ..."`

## 约定
- Python 路径: `/d/software/system/miniconda/python`
- 选科匹配用单字: `"化" in combo`, `"生" in combo`
- 启动前先查端口: `netstat -ano | grep 8083`
