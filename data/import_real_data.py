"""Import ALL 2707 schools' data using pre-saved file list."""
import asyncio, json, urllib.request, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

BASE = "https://raw.githubusercontent.com/1837620622/gaokao-admission-crawler/main"


async def import_all():
    from app.database import get_db
    db = await get_db()

    # Load file list
    with open(Path(__file__).parent / "gaokao_file_list.json") as f:
        files = json.load(f)

    print(f"Total files: {len(files)}", flush=True)

    cur = await db.execute_fetchall("SELECT COUNT(*) FROM admission_records")
    before = cur[0][0]
    print(f"Records before: {before}", flush=True)
    cur = await db.execute_fetchall("SELECT COUNT(*) FROM universities")
    univ_before = cur[0][0]
    print(f"Universities before: {univ_before}", flush=True)

    # Delete old GAOKAO_CN data to avoid duplicates
    await db.execute("DELETE FROM admission_records WHERE source='GAOKAO_CN'")
    await db.commit()
    print("Cleared old GAOKAO_CN records", flush=True)

    inserted = 0
    errors = 0
    skipped = 0
    univ_inserted = 0
    t0 = time.time()

    for i, filepath in enumerate(files):
        if i % 100 == 0:
            elapsed = time.time() - t0
            rate = (i / elapsed) if elapsed > 0 else 0
            pct = i * 100 // len(files)
            print(f"Progress: {i}/{len(files)} ({pct}%) inserted={inserted} errors={errors} skipped={skipped} {rate:.1f}files/s", flush=True)
            await db.commit()

        url = f"{BASE}/{filepath}"
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            encoded_path = urllib.parse.quote(parsed.path, safe='/:@!$&()*+,;=-._~')
            url_encoded = urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment)
            )
            resp = urllib.request.urlopen(url_encoded, timeout=30)
            data = json.loads(resp.read().decode())
        except Exception as e:
            errors += 1
            if errors <= 5:
                fn = filepath.split("/")[-1][:30]
                print(f"  DL error [{i}]: {fn}... {str(e)[:60]}", flush=True)
            continue

        uni_name = data.get('name', '')
        records = data.get('records', [])

        if not records:
            skipped += 1
            continue

        # Insert university (use INSERT OR IGNORE to handle duplicates)
        await db.execute(
            "INSERT OR IGNORE INTO universities (name, code, level, province) VALUES (?, ?, ?, ?)",
            (uni_name, data.get('code', ''), data.get('level', ''), data.get('province', ''))
        )

        for rec in records:
            try:
                province = rec.get('local_province_name', '')
                category = rec.get('local_type_name', '物理类')
                score = rec.get('min') or 0
                rank = rec.get('min_section') or 0
                subject = rec.get('sg_info', '不限')
                batch = rec.get('local_batch_name', '')
                major = rec.get('sg_name', '综合类')

                if not province or not score:
                    continue

                await db.execute(
                    "INSERT INTO admission_records (university_id, year, target_province, category, subject_requirement, group_name, min_score, min_rank, major_category, tuition, is_sino_foreign, source, confidence) VALUES ((SELECT id FROM universities WHERE name=? LIMIT 1),2025,?,?,?,?,?,?,?,0,0,'GAOKAO_CN','HIGH')",
                    (uni_name, province, category, subject, batch, score, rank, major)
                )
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  DB error: {str(e)[:80]}", flush=True)

    await db.commit()

    elapsed = time.time() - t0
    cur = await db.execute_fetchall("SELECT COUNT(*) FROM admission_records")
    cur2 = await db.execute_fetchall("SELECT COUNT(DISTINCT target_province) FROM admission_records")
    cur3 = await db.execute_fetchall("SELECT COUNT(DISTINCT university_id) FROM admission_records")
    cur4 = await db.execute_fetchall("SELECT COUNT(*) FROM universities")

    print(f"\n{'=' * 50}", flush=True)
    print("=== IMPORT RESULTS ===", flush=True)
    print(f"{'=' * 50}", flush=True)
    print(f"Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)", flush=True)
    print(f"Files processed: {i + 1}", flush=True)
    print(f"Records inserted: {inserted}", flush=True)
    print(f"New universities added: {cur4[0][0] - univ_before}", flush=True)
    print(f"Total universities: {cur4[0][0]}", flush=True)
    print(f"Download errors: {errors}", flush=True)
    print(f"Skipped (empty): {skipped}", flush=True)
    print(f"Total records: {cur[0][0]}", flush=True)
    print(f"Provinces covered: {cur2[0][0]}", flush=True)
    print(f"Universities with data: {cur3[0][0]}", flush=True)
    print(f"\nTop provinces:", flush=True)
    cur5 = await db.execute_fetchall(
        "SELECT target_province, COUNT(*) FROM admission_records GROUP BY target_province ORDER BY COUNT(*) DESC LIMIT 15"
    )
    for r in cur5:
        print(f"  {r[0]}: {r[1]}", flush=True)
    await db.close()


asyncio.run(import_all())
