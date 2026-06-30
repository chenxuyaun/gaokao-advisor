"""Import real gaokao.cn admission data - targeted approach by province."""
import asyncio, json, urllib.request, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Direct URLs for schools with data for specific provinces  
# Format: https://raw.githubusercontent.com/1837620622/gaokao-admission-crawler/main/gaokao_data/{id}_{url_encoded_name}.json

# Key schools for 四川 with their IDs from the dataset
SICHUAN_SCHOOLS = [
    (48, "北京邮电大学"), (42, "武汉大学"), (60, "天津大学"),
    (30, "北京工业大学"), (46, "中国人民大学"), (57, "西安电子科技大学"),
    (52, "北京师范大学"), (53, "对外经济贸易大学"), (61, "中国海洋大学"),
    (31, "北京大学"), (32, "内蒙古大学"), (33, "大连海事大学"),
    (34, "哈尔滨工业大学"), (35, "云南大学"), (36, "长安大学"),
    (37, "西北大学"), (38, "北京交通大学"), (39, "北京外国语大学"),
    (41, "河北工业大学"), (43, "北京林业大学"), (44, "湖南大学"),
    (45, "中央民族大学"), (47, "北京航空航天大学"), (49, "北京中医药大学"),
    (50, "辽宁大学"), (51, "西南交通大学"), (54, "河北大学"),
    (55, "河北科技大学"), (56, "河北经贸大学"),
]

BASE = "https://raw.githubusercontent.com/1837620622/gaokao-admission-crawler/main/gaokao_data"
TARGET_PROVINCES = ["四川", "广东", "河南", "江苏", "湖北", "湖南", "山东", "浙江", "河北", "安徽"]

async def import_data():
    from app.database import get_db
    db = await get_db()
    inserted = 0
    
    for school_id, school_name in SICHUAN_SCHOOLS:
        # URL encode Chinese name
        name_enc = urllib.request.quote(school_name, safe='')
        url = f"{BASE}/{school_id:05d}_{name_enc}.json"
        print(f"Fetching: {school_name}...", end=" ")
        
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"FAIL: {e}")
            continue
        
        # Process records for target provinces
        count = 0
        for rec in data.get('records', []):
            province = rec.get('local_province_name', '')
            if province not in TARGET_PROVINCES:
                continue
            
            category = rec.get('local_type_name', '物理类')
            score = rec.get('min') or 0
            rank = rec.get('min_section') or 0
            subject = rec.get('sg_info', '不限')
            batch = rec.get('local_batch_name', '')
            major = rec.get('sg_name', '综合类')
            
            if not score:
                continue
            
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO admission_records (university_id, year, target_province, category, subject_requirement, group_name, min_score, min_rank, major_category, tuition, is_sino_foreign, source, confidence) VALUES ((SELECT id FROM universities WHERE name=? LIMIT 1),2025,?,?,?,?,?,?,?,0,0,'GAOKAO_CN','HIGH')",
                    (school_name, province, category, subject, batch, score, rank, major)
                )
                count += 1
                inserted += 1
            except:
                pass
        
        print(f"OK ({count} records)")
        await db.commit()
    
    await db.commit()
    total = (await db.execute_fetchall("SELECT COUNT(*) FROM admission_records"))[0][0]
    print(f"\nDone! Inserted {inserted} records. Total: {total}")

asyncio.run(import_data())
