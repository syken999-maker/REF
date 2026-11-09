"""매일 수집한 후보를 feed.json 에 합친다.
사용: python3 add_to_feed.py <site폴더> <후보.json> <YYYY-MM-DD>
후보 항목: url, title, category, region, year, verified(true만 반영). credit·note·tags는 쓰지 않는다.
"""
import hashlib, json, re, sys, time
from pathlib import Path

base, cand_path, date = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
CATS = {"뮤직비디오", "광고", "시네마틱 필름", "모션그래픽", "FILM"}
feed_path = base / "feed.json"
feed = json.loads(feed_path.read_text(encoding="utf8")) if feed_path.exists() else []

known = {f["url"] for f in feed}
for p in base.glob("data*.json"):          # 처음 내장한 목록도 중복 검사
    for r in json.loads(p.read_text(encoding="utf8")):
        known.add(r["url"].strip())

yt = re.compile(r"^https://www\.youtube\.com/watch\?v=[\w-]{11}$")
vm = re.compile(r"^https://vimeo\.com/\d{5,}$")
added, rejected = 0, []
t0 = int(time.time() * 1000)
for r in json.loads(cand_path.read_text(encoding="utf8")):
    url = r.get("url", "").strip()
    why = None
    if not r.get("verified"): why = "unverified"
    elif not (yt.match(url) or vm.match(url)): why = "bad-url"
    elif url in known: why = "duplicate"
    elif r.get("category") not in CATS: why = "bad-category"
    if why:
        rejected.append((url, why)); continue
    known.add(url)
    feed.append({
        "id": "f" + hashlib.sha1(url.encode()).hexdigest()[:10], "url": url,
        "title": r.get("title", "").strip(), "credit": "",
        "category": r["category"], "date": date, "region": r.get("region", ""),
        "year": r.get("year", 0), "tags": [],
        "note": "", "fav": False, "createdAt": t0 + added,
    })
    added += 1
feed_path.write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf8")
print("added", added, "total", len(feed), "rejected", rejected)
