# 高考志愿顾问 Gaokao Advisor — 实施计划

> **For Hermes:** 按步骤执行，每步完成后再进入下一步。优先构建MVP（四川单省），验证后扩展全国。

**Goal:** 构建一个免费的在线高考志愿分析推荐网站，支持输入分数→位次计算→院校推荐→导出报告

**Architecture:** FastAPI后端 + SQLite数据层 + 纯HTML/CSS/JS前端，单文件部署，Docker容器化

**Tech Stack:** Python 3.11, FastAPI, SQLite, uvicorn, Nginx, Docker

---

## Phase 1: 项目骨架 + 数据库设计 (预计1h)

### Task 1.1: 初始化项目结构

**Objective:** 创建完整的项目目录和配置文件

**Files:**
- Create: `D:\gaokao-advisor\backend\app\__init__.py`
- Create: `D:\gaokao-advisor\backend\app\main.py`
- Create: `D:\gaokao-advisor\backend\app\database.py`
- Create: `D:\gaokao-advisor\backend\app\models.py`
- Create: `D:\gaokao-advisor\backend\app\routers\__init__.py`
- Create: `D:\gaokao-advisor\backend\app\routers\recommend.py`
- Create: `D:\gaokao-advisor\backend\app\routers\data.py`
- Create: `D:\gaokao-advisor\backend\requirements.txt`
- Create: `D:\gaokao-advisor\frontend\index.html`
- Create: `D:\gaokao-advisor\docker-compose.yml`
- Create: `D:\gaokao-advisor\Dockerfile`
- Create: `D:\gaokao-advisor\nginx.conf`

### Task 1.2: 数据库Schema设计

**Objective:** 创建SQLite表结构，支持省份、分数线、一分一段、院校、录取数据

```sql
-- provinces: 省份+年份+类别+批次线
CREATE TABLE provinces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,          -- 四川
    year INTEGER NOT NULL,       -- 2026
    category TEXT NOT NULL,      -- 物理类/历史类
    batch TEXT NOT NULL,         -- 本科批/特殊类型
    score INTEGER NOT NULL,      -- 435/519
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- score_segments: 一分一段表
CREATE TABLE score_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    province_id INTEGER REFERENCES provinces(id),
    score INTEGER NOT NULL,      -- 591
    cumulative_count INTEGER,    -- 累计人数 29671
    section_count INTEGER,       -- 同分人数
    year INTEGER NOT NULL
);

-- universities: 院校信息
CREATE TABLE universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,           -- 温州医科大学
    code TEXT,                    -- 院校代码
    level TEXT,                   -- 985/211/双一流/普通
    province TEXT,                -- 所在省份
    city TEXT,                    -- 所在城市
    is_public BOOLEAN DEFAULT 1,
    website TEXT
);

-- admission_records: 历年录取数据（核心表）
CREATE TABLE admission_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER REFERENCES universities(id),
    year INTEGER NOT NULL,
    target_province TEXT NOT NULL,   -- 四川（考生省份）
    category TEXT NOT NULL,          -- 物理类
    subject_requirement TEXT,        -- 化学+生物（再选科目要求）
    group_name TEXT,                 -- 专业组108
    min_score INTEGER NOT NULL,      -- 最低录取分
    min_rank INTEGER,                -- 最低位次
    avg_score INTEGER,               -- 平均分
    major_category TEXT,             -- 专业大类
    tuition INTEGER,                 -- 学费
    is_sino_foreign BOOLEAN DEFAULT 0,
    notes TEXT
);

-- majors: 专业信息+就业数据
CREATE TABLE majors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,                -- 医学/工学/理学
    subject_requirements TEXT,    -- 物化生推荐选科
    avg_salary_5yr INTEGER,       -- 5年平均薪资
    employment_rate REAL,         -- 就业率
    career_path TEXT,             -- 就业方向描述
    zhang_xuefeng_comment TEXT    -- 张雪峰风格点评
);
```

### Task 1.3: 种子数据导入

**Objective:** 导入2026四川分数线 + 2025四川一分一段表 + 已搜索到的院校录取数据

**Files:**
- Create: `D:\gaokao-advisor\data\seed_sichuan_2026.py`
- Create: `D:\gaokao-advisor\data\seed_sichuan_admissions_2025.py`

## Phase 2: 后端API (预计2h)

### Task 2.1: FastAPI基础框架

**Objective:** 创建FastAPI应用，连接SQLite，启动服务

**Files to create:**
- `D:\gaokao-advisor\backend\app\main.py` — FastAPI app + CORS + static mount
- `D:\gaokao-advisor\backend\app\database.py` — SQLite连接 + session管理

```python
# main.py skeleton
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.routers import recommend, data

app = FastAPI(title="高考志愿顾问", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
app.include_router(recommend.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

@app.on_event("startup")
async def startup():
    await init_db()
```

### Task 2.2: 推荐引擎核心算法

**Objective:** 实现位次估算 + 冲稳保分层推荐

**Files:**
- Create: `D:\gaokao-advisor\backend\app\engine.py`

**Algorithm:**
```
1. 输入：省份 + 分数 + 类别(物理/历史) + 选科组合
2. 查一分一段表 → 获取精确位次 rank
3. 冲 (冲刺): rank * 0.85 ~ rank * 0.97  → ±5分位次范围向上
4. 稳 (稳妥): rank * 0.97 ~ rank * 1.05  → ±3分位次范围
5. 保 (保底): rank * 1.05 ~ rank * 1.30  → -10分位次范围向下
6. 在每个区间查询 admission_records，按选科要求筛选
7. 返回分组结果
```

### Task 2.3: API端点

**Objective:** 实现所有REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/provinces` | GET | 获取省份列表+分数线 |
| `/api/rank/{province}/{score}/{category}` | GET | 分数→位次查询 |
| `/api/recommend` | POST | 核心推荐接口 |
| `/api/university/{id}` | GET | 院校详情 |
| `/api/majors` | GET | 专业列表+就业数据 |
| `/api/score-segments/{province}/{year}` | GET | 一分一段表查询 |
| `/api/sync` | POST | 触发数据同步 |

### Task 2.4: 数据同步Pipeline

**Objective:** 实现定时从公开数据源同步最新分数线

```python
# 从四川省教育考试院 / 中国教育在线抓取最新数据
# 使用 cron 定时执行
```

## Phase 3: 前端页面 (预计2h)

### Task 3.1: Notion风格设计系统

**Objective:** 实现Notion风格的基础CSS变量和组件

使用 `popular-web-designs` skill 中的 Notion 设计系统：
- 暖色调中性色 (`#f6f5f4`, `#615d59`, `rgba(0,0,0,0.95)`)
- Inter字体 + 压缩字间距
- Whisper边框 (`1px solid rgba(0,0,0,0.1)`)
- 多层阴影 (4层，max opacity 0.04)
- 蓝调CTA按钮 (`#0075de`)

### Task 3.2: 输入表单页

**Objective:** 构建分数输入+选科选择的表单

- 省份下拉选择（默认四川）
- 分数输入框（滑块+数字输入）
- 选科组合选择（物化生/物化地/...）
- 高级筛选：地域偏好/专业方向/学费范围
- 搜索按钮 → 调用 `/api/recommend`

### Task 3.3: 结果展示页

**Objective:** 冲稳保三栏结果展示

- 三栏布局：🔴冲刺 | 🟡稳妥 | 🟢保底
- 每栏：院校卡片（名称/专业组/分数/位次/选科要求）
- 专业推荐列表
- 张雪峰风格点评文案
- 一键导出PDF / 分享链接

### Task 3.4: 数据可视化

**Objective:** 位次分布图+历年趋势图

- 位次仪表盘（你的位次 vs 省控线）
- 历年录取分数趋势折线图（纯Canvas，无Chart.js依赖）
- 同分位次院校分布散点图

## Phase 4: 部署 (预计0.5h)

### Task 4.1: Docker配置

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/
EXPOSE 8082
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8082"]
```

### Task 4.2: Nginx配置

```nginx
server {
    listen 80;
    server_name gaokao.example.com;
    location / {
        proxy_pass http://127.0.0.1:8082;
    }
}
```

### Task 4.3: docker-compose一键部署

```yaml
version: '3.8'
services:
  app:
    build: .
    ports: ["8082:8082"]
    volumes:
      - ./data:/app/data
    restart: always
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
```

## Phase 5: 全国扩展 (后续迭代)

- 添加31省分数线数据
- 多省份一分一段表
- 全国院校录取数据库
- 专业就业数据完善
- 用户系统（可选）
- 志愿表模拟填报

---

## 验证清单

- [ ] `uvicorn backend.app.main:app` 启动成功
- [ ] `curl localhost:8082/api/provinces` 返回JSON
- [ ] 输入591分+四川+物理+物化生 → 返回推荐列表
- [ ] 前端页面加载 < 2秒
- [ ] 手机浏览器显示正常
- [ ] Docker build + run 成功
