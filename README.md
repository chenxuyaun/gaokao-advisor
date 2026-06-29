# 🎓 高考志愿顾问 Gaokao Advisor

> AI-driven 高考志愿填报分析推荐系统 — 输入分数，AI 帮你选专业、选学校

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🇨🇳 这是什么

一个**完全免费**的高考志愿分析系统，覆盖全国31个省份。输入你的省份、分数、选科，AI就能：

- 🎯 **推荐专业** — 根据你的位次匹配适合的学校和专业
- 🤖 **AI 职业分析** — 张雪峰风格的就业导向分析
- 🔍 **实时搜索** — 搜索最新就业市场数据，不用过时信息
- 📊 **录取概率** — 估算每所大学的录取概率
- 📋 **专业对比** — 7维度评分对比不同专业
- 🗺️ **路径规划** — 生成就业/考研/考公/创业路径
- 💬 **家长问答** — AI动态生成针对性问题

## 🚀 快速开始

### 本地运行

```bash
cd backend
pip install -r requirements.txt
cd ..
python data/seed_unified.py
uvicorn backend.app.main:app --host 0.0.0.0 --port 8083
```

打开 `http://localhost:8083`

### Docker

```bash
docker build -t gaokao-advisor .
docker run -p 7860:7860 -e DEEPSEEK_API_KEY=sk-xxx gaokao-advisor
```

## 🔧 技术栈

| 组件 | 技术 |
|:----|:-----|
| 后端 | Python 3.11 + FastAPI |
| 数据库 | SQLite (aiosqlite) |
| AI | DeepSeek API |
| 搜索 | Wikipedia + 360 + DuckDuckGo |
| 前端 | 纯 HTML + JavaScript |
| 部署 | Docker + HuggingFace Spaces |

## 📂 项目结构

```
gaokao-advisor/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI 入口
│       ├── engine.py             # 位次估算 + 分数线查询
│       ├── searcher.py           # 三引擎搜索模块
│       ├── routers/
│       │   ├── recommend_v3.py   # AI驱动推荐（核心）
│       │   ├── recommend_v2.py   # 传统推荐（备用）
│       │   ├── ask.py            # 家长问答 + AI动态问题
│       │   ├── ai_features.py    # 录取概率/对比/路径规划
│       │   └── data.py           # 数据查询接口
│       └── models.py            # 数据模型
├── frontend/
│   └── index.html               # 单页前端
├── data/
│   ├── seed_unified.py          # 统一种子数据脚本
│   └── universities_expanded.py # 283所大学数据
├── Dockerfile
└── README.md
```

## 📊 数据

- **31省** 2026年高考分数线 + 一分一段表
- **283所大学**（985/211/双一流全覆盖）
- **107个专业**（7种选科组合）

数据在 Docker 构建时自动初始化，无需手动导入。

## ⚙️ 环境变量

| 变量 | 必填 | 说明 |
|:----|:----:|:-----|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key（[获取](https://platform.deepseek.com/)） |

## 📄 License

MIT License — 可自由使用、修改、商用。

## 🤝 贡献

欢迎 Issue 和 PR！如果你有新功能建议或发现了bug，直接提 Issue。
