"""FastAPI application entry point."""
import sys
from pathlib import Path

# Ensure backend/ is on the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import init_db
from app.routers import recommend, data, recommend_v2, recommend_v3, ask, ai_features

app = FastAPI(
    title="高考志愿顾问 Gaokao Advisor",
    description="免费高考志愿分析推荐系统 — 输入分数，智能匹配院校和专业",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(recommend_v2.router, prefix="/api")
app.include_router(recommend_v3.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(ai_features.router)


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/api/health")
async def health():
    import os
    has_ai = bool(os.getenv("DEEPSEEK_API_KEY", ""))
    return {"status": "ok", "version": "2.1.0", "ai_ready": has_ai}


# Mount frontend AFTER all routes — otherwise StaticFiles at "/" intercepts /api/*
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
