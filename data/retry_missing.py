"""Retry importing ALL schools that are still missing from the DB."""
import json, urllib.request, sqlite3, urllib.parse, time, ssl, sys
from pathlib import Path

files = json.load(open(Path(__file__).parent / "gaokao_file_list.json"))
conn = sqlite3.connect(str(Path(__file__).parent.parent / "data" / "gaokao.db"))

# Get DB names with GAOKAO_CN data
db_names = set()
for r in conn.execute(
    "SELECT u.name FROM admission_records ar JOIN universities u ON ar.university_id=u.id WHERE ar.source='GAOKAO_CN' GROUP BY u.id"
):
    db_names.add(r[0])
conn.close()

BASE = "https://raw.githubusercontent.com/1837620622/gaokao-admission-crawler/main"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

conn = sqlite3.connect(str(Path(__file__).parent.parent / "data" / "gaokao.db"))
inserted = 0
errors = 0
skipped = 0
checked = 0
truly_missing = 0

for i, fp in enumerate(files):
    try:
        url = BASE + "/" + fp
        parsed = urllib.parse.urlparse(url)
        encoded_path = urllib.parse.quote(parsed.path, safe="/:@!$&()*+,;=-._~")
        url_enc = urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment)
        )

        resp = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url_enc, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=30, context=ctx)
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(5)
                else:
                    raise e

        data = json.loads(resp.read().decode())
        checked += 1

        uni_name = data.get("name", "")
        if uni_name in db_names:
            skipped += 1
            continue

        truly_missing += 1
        records = data.get("records", [])
        if not records:
            continue

        conn.execute(
            "INSERT OR IGNORE INTO universities (name, code, level, province) VALUES (?, ?, ?, ?)",
            (uni_name, data.get("code", ""), data.get("level", ""), data.get("province", "")),
        )

        for rec in records:
            try:
                province = rec.get("local_province_name", "")
                category = rec.get("local_type_name", "物理类")
                score = rec.get("min") or 0
                rank = rec.get("min_section") or 0
                subject = rec.get("sg_info", "不限")
                batch = rec.get("local_batch_name", "")
                major = rec.get("sg_name", "综合类")
                if not province or not score:
                    continue
                conn.execute(
                    "INSERT INTO admission_records (university_id, year, target_province, category, subject_requirement, group_name, min_score, min_rank, major_category, tuition, is_sino_foreign, source, confidence) VALUES ((SELECT id FROM universities WHERE name=? LIMIT 1),2025,?,?,?,?,?,?,?,0,0,'GAOKAO_CN','HIGH')",
                    (uni_name, province, category, subject, batch, score, rank, major),
                )
                inserted += 1
            except Exception:
                pass

    except Exception as e:
        errors += 1
        if errors <= 10:
            print(f"FAIL[{i}]: {fp.split('/')[-1][:30]} - {str(e)[:60]}", flush=True)

    if i > 0 and i % 300 == 0:
        conn.commit()
        print(
            f"[{i}/{len(files)}] checked={checked} imported={inserted} missing={truly_missing} errors={errors} skipped={skipped}",
            flush=True,
        )

conn.commit()

final_total = conn.execute("SELECT COUNT(*) FROM admission_records").fetchone()[0]
final_schools = conn.execute("SELECT COUNT(DISTINCT university_id) FROM admission_records WHERE source='GAOKAO_CN'").fetchone()[0]
final_univs = conn.execute("SELECT COUNT(*) FROM universities").fetchone()[0]

print("\n=== FINAL RESULTS ===", flush=True)
print(f"Total admission_records: {final_total}", flush=True)
print(f"Schools with GAOKAO_CN data: {final_schools}/2707", flush=True)
print(f"Universities in DB: {final_univs}", flush=True)
print(f"New records from retry: {inserted}", flush=True)
print(f"Download errors: {errors}", flush=True)
print(f"Already in DB (skipped): {skipped}", flush=True)
print(f"Truly missing schools found: {truly_missing}", flush=True)
conn.close()
