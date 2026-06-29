"""Comprehensive seed script — expands universities to 283, majors to 57, provinces to 31."""
import asyncio, sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.database import init_db, get_db

# ===== Load expanded data =====
exec(open(Path(__file__).parent / "universities_expanded.py").read())
exec(open(Path(__file__).parent / "majors_expanded.py").read())

async def seed_all(db):
    # ===== 1. Already done: provinces (31 provinces with cutoffs) =====
    count = await db.execute_fetchall("SELECT COUNT(DISTINCT name) FROM provinces")
    print(f"[seed] Provinces: {count[0][0]}/31")

    # ===== 2. Universities: insert 283 =====
    uni_count = 0
    for name, level, province, city in UNIVERSITIES_EXPANDED:
        await db.execute(
            "INSERT OR IGNORE INTO universities (name, level, province, city, website) VALUES (?, ?, ?, ?, ?)",
            (name, level, province, city, "")
        )
        uni_count += 1
    await db.commit()
    actual = await db.execute_fetchall("SELECT COUNT(*) FROM universities")
    print(f"[seed] Universities: inserted {uni_count}, total: {actual[0][0]}")

    # ===== 3. Majors: insert 57 =====
    major_count = 0
    for name, cat, sub_req, salary, emp_rate, career, comment in MAJORS_EXPANDED:
        await db.execute(
            """INSERT OR IGNORE INTO majors
               (name, category, subject_requirements, avg_salary_5yr, employment_rate, career_path, zhang_xuefeng_comment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, cat, sub_req, salary, emp_rate, career, comment)
        )
        major_count += 1
    await db.commit()
    actual = await db.execute_fetchall("SELECT COUNT(*) FROM majors")
    print(f"[seed] Majors: inserted {major_count}, total: {actual[0][0]}")

    # ===== 4. Score segments for major provinces =====
    # Use cutoff points so estimate_rank can interpolate
    # Format: (province, year, category, score, cumulative_count, section_count)
    # Top and bottom anchors + key cutoffs
    segments = []
    
    # All province cutoff data with approximate rank estimates
    # For 3+3: 综合, for old: 历史类/物理类
    province_segments = {
        # province: [(category, score, cumulative_count), ...]
        # Using known data points + estimates from total考生数
        "北京": [("综合", 521, 22000), ("综合", 429, 45000), ("综合", 400, 55000)],
        "天津": [("综合", 547, 18000), ("综合", 458, 42000), ("综合", 400, 55000)],
        "上海": [("综合", 504, 16000), ("综合", 403, 42000), ("综合", 350, 52000)],
        "浙江": [("综合", 594, 58000), ("综合", 494, 170000), ("综合", 450, 200000)],
        "山东": [("综合", 525, 130000), ("综合", 442, 310000), ("综合", 400, 350000)],
        "海南": [("综合", 568, 12000), ("综合", 479, 28000), ("综合", 400, 40000)],
        "广东": [("物理类", 539, 85000), ("物理类", 425, 260000), ("物理类", 400, 280000),
                 ("历史类", 546, 22000), ("历史类", 440, 90000), ("历史类", 400, 105000)],
        "河南": [("物理类", 513, 125000), ("物理类", 419, 310000), ("物理类", 400, 330000),
                 ("历史类", 534, 26000), ("历史类", 459, 90000), ("历史类", 400, 115000)],
        "江苏": [("物理类", 513, 80000), ("物理类", 456, 180000), ("物理类", 400, 210000),
                 ("历史类", 532, 22000), ("历史类", 484, 65000), ("历史类", 400, 90000)],
        "湖北": [("物理类", 529, 60000), ("物理类", 435, 180000), ("物理类", 400, 210000),
                 ("历史类", 532, 15000), ("历史类", 443, 60000), ("历史类", 400, 75000)],
        "湖南": [("物理类", 481, 100000), ("物理类", 400, 240000), ("物理类", 380, 260000),
                 ("历史类", 494, 25000), ("历史类", 446, 70000), ("历史类", 400, 92000)],
        "河北": [("物理类", 510, 100000), ("物理类", 443, 220000), ("物理类", 400, 250000),
                 ("历史类", 542, 25000), ("历史类", 485, 70000), ("历史类", 400, 100000)],
        "四川": [("物理类", 519, 100000), ("物理类", 435, 200000), ("物理类", 400, 220000),
                 ("历史类", 525, 30000), ("历史类", 455, 80000), ("历史类", 400, 105000)],
        "安徽": [("物理类", 514, 70000), ("物理类", 451, 160000), ("物理类", 400, 190000),
                 ("历史类", 522, 18000), ("历史类", 490, 45000), ("历史类", 400, 70000)],
        "福建": [("物理类", 528, 45000), ("物理类", 446, 110000), ("物理类", 400, 135000),
                 ("历史类", 533, 10000), ("历史类", 458, 35000), ("历史类", 400, 47000)],
        "江西": [("物理类", 505, 60000), ("物理类", 412, 180000), ("物理类", 400, 190000),
                 ("历史类", 535, 15000), ("历史类", 479, 50000), ("历史类", 400, 72000)],
        "辽宁": [("物理类", 508, 48000), ("物理类", 344, 120000), ("物理类", 300, 130000),
                 ("历史类", 527, 12000), ("历史类", 442, 35000), ("历史类", 300, 58000)],
        "重庆": [("物理类", 496, 45000), ("物理类", 406, 110000), ("物理类", 350, 130000),
                 ("历史类", 510, 12000), ("历史类", 415, 40000), ("历史类", 350, 52000)],
        "陕西": [("物理类", 451, 60000), ("物理类", 376, 130000), ("物理类", 350, 145000),
                 ("历史类", 462, 15000), ("历史类", 385, 45000), ("历史类", 350, 54000)],
        "云南": [("物理类", 505, 50000), ("物理类", 435, 110000), ("物理类", 400, 125000),
                 ("历史类", 545, 12000), ("历史类", 465, 42000), ("历史类", 400, 55000)],
        "贵州": [("物理类", 494, 45000), ("物理类", 393, 150000), ("物理类", 350, 170000),
                 ("历史类", 503, 15000), ("历史类", 439, 55000), ("历史类", 350, 75000)],
        "广西": [("物理类", 510, 45000), ("物理类", 368, 150000), ("物理类", 350, 160000),
                 ("历史类", 520, 12000), ("历史类", 398, 55000), ("历史类", 350, 68000)],
        "山西": [("物理类", 524, 30000), ("物理类", 401, 100000), ("物理类", 350, 120000),
                 ("历史类", 538, 7000), ("历史类", 409, 38000), ("历史类", 350, 48000)],
        "黑龙江": [("物理类", 464, 35000), ("物理类", 340, 100000), ("物理类", 300, 115000),
                   ("历史类", 466, 9000), ("历史类", 385, 35000), ("历史类", 300, 45000)],
        "吉林": [("物理类", 473, 25000), ("物理类", 321, 80000), ("物理类", 300, 89000),
                 ("历史类", 478, 6500), ("历史类", 343, 30000), ("历史类", 300, 36000)],
        "甘肃": [("物理类", 477, 35000), ("物理类", 367, 95000), ("物理类", 350, 102000),
                 ("历史类", 508, 9000), ("历史类", 405, 40000), ("历史类", 350, 50000)],
        "内蒙古": [("物理类", 488, 25000), ("物理类", 363, 70000), ("物理类", 350, 76000),
                   ("历史类", 512, 6500), ("历史类", 403, 23000), ("历史类", 350, 29000)],
        "新疆": [("物理类", 468, 18000), ("物理类", 304, 70000), ("物理类", 250, 85000),
                 ("历史类", 451, 6500), ("历史类", 315, 32000), ("历史类", 250, 42000)],
        "宁夏": [("物理类", 437, 15000), ("物理类", 360, 45000), ("物理类", 300, 55000),
                 ("历史类", 474, 5000), ("历史类", 393, 18000), ("历史类", 300, 25000)],
        "青海": [("物理类", 417, 8000), ("物理类", 344, 25000), ("物理类", 300, 31000),
                 ("历史类", 427, 3500), ("历史类", 376, 12000), ("历史类", 300, 16000)],
        "西藏": [("物理类", 400, 5000), ("物理类", 300, 15000), ("物理类", 250, 20000),
                 ("历史类", 400, 3000), ("历史类", 304, 10000), ("历史类", 250, 14000)],
    }

    seg_count = 0
    for prov, entries in province_segments.items():
        for cat, score, cum in entries:
            await db.execute(
                "INSERT OR REPLACE INTO score_segments (province_name, year, category, score, cumulative_count, section_count) VALUES (?, ?, ?, ?, ?, ?)",
                (prov, 2026, cat, score, cum, None)
            )
            seg_count += 1
    await db.commit()
    actual = await db.execute_fetchall("SELECT COUNT(DISTINCT province_name) FROM score_segments")
    print(f"[seed] Score segments: inserted {seg_count}, covering {actual[0][0]} provinces")

    # ===== 5. Preserve existing admission records (四川 only) =====
    adm = await db.execute_fetchall("SELECT COUNT(*) FROM admission_records")
    print(f"[seed] Admission records preserved: {adm[0][0]} (四川 only)")

    print("\n✅ Seed complete!")

async def main():
    await init_db()
    db = await get_db()
    try:
        await seed_all(db)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
