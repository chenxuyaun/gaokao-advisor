# 高考志愿顾问 — 剩余任务规划

## 优先级 P0（核心问题，影响使用）

### P0-1: 导入全部2707所学校的真实录取数据
- **现状**: 只导入了28所（1937条记录）
- **目标**: 全部2707所（14.3万条记录）
- **阻碍**: GitHub API 限速 + SSL 环境限制
- **方案**:
  1. 在本地用 Python 通过 `raw.githubusercontent.com` 直接下载每个 JSON 文件（不经过 API）
  2. 文件命名模式: `{id:05d}_{urlencoded_name}.json`，ID 从 30 到 3000+
  3. 遍历 ID，尝试下载，404 的跳过
  4. 预计耗时: 2707个文件 × 2秒 = ~90分钟
  5. 或：让 cron 定时器每次跑30分钟，分多次完成

### P0-2: 覆盖全部31省
- **现状**: 只有10省有真实数据（缺失21省：北京/上海/天津/福建/江西/辽宁/重庆/陕西/云南/贵州/广西/山西/黑龙江/吉林/甘肃/内蒙古/新疆/宁夏/青海/西藏/海南）
- **方案**: 导入全部数据后自然覆盖

## 优先级 P1（重要但不紧急）

### P1-1: 学校名称匹配优化
- **现状**: import 脚本用 `SELECT id FROM universities WHERE name=?` 精确匹配，但 gaokao.cn 的学校名称可能与我们的列表不完全一致
- **方案**: 改为模糊匹配 + 手工映射表

### P1-2: 清理废弃文件
- **现状**: 大量不再使用的旧文件
- **文件列表**:
  - `data/seed_sichuan.py` — 已被 seed_unified.py 替代
  - `data/seed_comprehensive.py` — 已被 seed_unified.py 替代
  - `data/seed_all_provinces.py` — 已被 seed_unified.py 替代
  - `data/seed_admissions_multi_province.py` — 不再需要（现在用真实数据）
  - `backend/app/routers/recommend.py` — v1 已废弃
  - `backend/app/routers/recommend_v2.py` — 已损坏（match_majors 返回空）
  - `backend/app/engine.py` 中的 MAJOR_QUALITY 注释

### P1-3: 更新 Dockerfile
- **现状**: Dockerfile 跑 seed_unified.py 生成模拟数据
- **方案**: 改为只生成 provinces + score_segments + universities + majors，不生成 admission_records（因为现在用真实数据）

## 优先级 P2（锦上添花）

### P2-1: 前端移动端适配
- **现状**: 页面在手机上可能显示不正常
- **方案**: 添加响应式 CSS

### P2-2: 新增功能
- 志愿表生成（冲-稳-保完整方案）
- 学校详情弹窗
- 招生简章查询

### P2-3: 定时器优化
- **现状**: 每30分钟运行一次
- **方案**: 改为先完成数据导入，再开启定期测试

## 执行顺序建议

```
第1步: P0-1 导入全部数据（写入 cron 定时器自动完成）
第2步: P0-2 验证31省覆盖
第3步: P1-1 学校名称匹配
第4步: P1-2 清理废弃文件
第5步: P1-3 更新 Dockerfile
第6步: P2-1/2/3 优化和新功能
```
