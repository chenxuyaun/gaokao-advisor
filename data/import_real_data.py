"""Fast concurrent import of ALL 2707 schools' data."""
import asyncio, json, urllib.request, sys, time, concurrent.futures
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

BASE = "https://raw.githubusercontent.com/1837620622/gaokao-admission-crawler/main"
WORKERS = 20  # concurrent downloads

def download_json(filepath):
    """Download a single JSON file (sync, runs in thread pool)."""
    url = f"{BASE}/{filepath}"
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        encoded = urllib.parse.quote(parsed.path, safe='/:@!$&()*+,;=-._~')
        url_enc = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, encoded, parsed.params, parsed.query, parsed.fragment))
        resp = urllib.request.urlopen(url_enc, timeout=30)
        return json.loads(resp.read().decode())
    except:
        return None

async def import_all():
    from app.database import get_db
    db = await get_db()
    
    with open(Path(__file__).parent / "gaokao_file_list.json") as f:
        files = json.load(f)
    
    print(f"Total files: {len(files)}", flush=True)
    
    cur = await db.execute_fetchall("SELECT COUNT(*) FROM admission_records")
    before = cur[0][0]
    cur2 = await db.execute_fetchall("SELECT COUNT(*) FROM universities")
    univ_before = cur2[0][0]
    print(f"Records: {before}, Universities: {univ_before}", flush=True)
    
    t0 = time.time()
    total_inserted = 0
    
    # Download files concurrently using thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        fut_map = {pool.submit(download_json, fp): i for i, fp in enumerate(files)}
        done = 0
        
        for fut in concurrent.futures.as_completed(fut_map):
            done += 1
            data = fut.result()
            if not data:
                if done % 200 == 0:
                    print(f"Progress: {done}/{len(files)} ({done*100//len(files)}%) inserted={total_inserted}", flush=True)
                continue
            
            uni_name = data.get('name', '')
            records = data.get('records', [])
            if not records:
                continue
            
            # Insert university
            await db.execute("INSERT OR IGNORE INTO universities (name, level, province) VALUES (?,?,?)",
                           (uni_name, data.get('level', ''), data.get('province', '')))
            
            batch_inserted = 0
            for rec in records:
                # Handle both format types: A has local_province_name, B uses local_province_id
                province = rec.get('local_province_name', '')
                if not province:
                    # Format B: use school's province + batch lookup
                    province = data.get('province', '')
                
                category = rec.get('local_type_name', '')
                if not category:
                    cat_id = rec.get('local_type_id', 0)
                    category = {1: '物理类', 2: '历史类', 3: '综合', 4: '艺术', 5: '体育'}.get(cat_id, '物理类')
                
                score = rec.get('min') or 0
                rank = rec.get('min_section') or 0
                subject = rec.get('sg_info', '不限')
                batch = rec.get('local_batch_name', '')
                if not batch:
                    batch_id = rec.get('local_batch_id', 0)
                    batch = {1: '本科批', 2: '本科提前批', 3: '专科批', 4: '艺术类', 5: '体育类', 7: '本科批'}.get(batch_id, '本科批')
                major = rec.get('sg_name', '综合类')
                if not major:
                    major = rec.get('sp_name', '综合类')  # Format B uses sp_name for major
                
                if not province or not score:
                    continue
                
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO admission_records (university_id, year, target_province, category, subject_requirement, group_name, min_score, min_rank, major_category, tuition, is_sino_foreign, source, confidence) VALUES ((SELECT id FROM universities WHERE name=? LIMIT 1),2025,?,?,?,?,?,?,?,0,0,'GAOKAO_CN','HIGH')",
                        (uni_name, province, category, subject, batch, score, rank, major)
                    )
                    batch_inserted += 1
                except:
                    pass
            
            total_inserted += batch_inserted
            
            if done % 100 == 0:
                print(f"Progress: {done}/{len(files)} ({done*100//len(files)}%) inserted={total_inserted}", flush=True)
                await db.commit()
    
    await db.commit()
    elapsed = time.time() - t0
    
    cur3 = await db.execute_fetchall("SELECT COUNT(*) FROM admission_records")
    cur4 = await db.execute_fetchall("SELECT COUNT(DISTINCT university_id) FROM admission_records WHERE source='GAOKAO_CN'")
    cur5 = await db.execute_fetchall("SELECT COUNT(DISTINCT target_province) FROM admission_records WHERE source='GAOKAO_CN'")
    
    print(f"\n{'='*50}", flush=True)
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f}min)", flush=True)
    print(f"New records: {total_inserted}", flush=True)
    print(f"Total records: {cur3[0][0]}", flush=True)
    print(f"Universities with data: {cur4[0][0]}", flush=True)
    print(f"Provinces: {cur5[0][0]}", flush=True)
    await db.close()

asyncio.run(import_all())
