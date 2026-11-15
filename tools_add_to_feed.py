"""매일 수집한 후보를 feed.json 에 합친다.
사용: python3 add_to_feed.py <site폴더> <후보.json> <YYYY-MM-DD>
후보 항목: url, title, category, region, year, published(YYYY-MM-DD 업로드 날짜, 선택), verified(true만 반영). credit·note·tags는 쓰지 않는다.
각 후보는 이 스크립트가 YouTube/Vimeo oEmbed를 직접 호출해 실재·임베드 가능 여부를 확인하고(실패하면 oembed-fail로 거부), 제목은 oEmbed 제목으로 저장한다.
"""
import hashlib, json, re, sys, time
from pathlib import Path

import urllib.error, urllib.parse, urllib.request

def oembed(url):
    """oEmbed로 영상이 실제로 있고 임베드 가능한지 확인한다. 실패하면 None."""
    if "vimeo.com" in url:
        api = "https://vimeo.com/api/oembed.json?url=" + urllib.parse.quote(url, safe="")
    else:
        api = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe="")
    req = urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0 (ref-feed-checker)"})
    for attempt in range(3):
        try:
            j = json.load(urllib.request.urlopen(req, timeout=20))
            return j if str(j.get("title", "")).strip() else None
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404):   # 없음·비공개·임베드 불가
                return None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None

base, cand_path, date = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
CATS = {"뮤직비디오", "광고", "시네마틱 필름", "모션그래픽", "애니메이션", "FILM"}
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
    meta = None
    if not why:
        meta = oembed(url)                      # 스크립트가 직접 존재·제목을 확인
        if not meta: why = "oembed-fail"
    if why:
        rejected.append((url, why)); continue
    pub = str(r.get("published") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", pub):
        pub = str(meta.get("upload_date") or "")[:10]   # Vimeo만 제공
    known.add(url)
    feed.append({
        "id": "f" + hashlib.sha1(url.encode()).hexdigest()[:10], "url": url,
        "title": str(meta["title"]).strip(), "credit": "",
        "category": r["category"], "date": date, "region": r.get("region", ""),
        "year": r.get("year", 0), "tags": [],
        "note": "", "fav": False, "createdAt": t0 + added,
        "published": pub,
    })
    added += 1
feed_path.write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf8")
print("added", added, "total", len(feed), "rejected", rejected)
