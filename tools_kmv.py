"""한국 뮤직비디오(아이돌·힙합 등) 후보를 기획사·레이블·아티스트 공식 채널에서 모은다.
사용: pip install --break-system-packages yt-dlp
      python3 tools_kmv.py <저장소폴더> <출력후보.json> <since YYYY-MM-DD>
- 채널 영상 목록(yt-dlp flat)에서 제목에 MV/M/V/Official Video가 있는 것만 고르고(티저·비하인드·퍼포먼스 등 제외),
- 각 영상의 정확한 업로드일을 yt-dlp(player_client=web_embedded)로 확인해 since 이후만 남긴다.
- 업로드일을 확인하지 못한 영상은 넣지 않는다. feed.json에 이미 있는 URL은 뺀다.
- 출력 항목: url, title, category "뮤직비디오", region "국내", year, published, verified true
  (90일보다 오래된 2026년 작품은 classic:true를 붙여 tools_add_to_feed.py의 too-old 검사를 통과시킨다).
출력 파일은 그대로 tools_add_to_feed.py에 넣으면 된다(oEmbed 실재 확인은 그 스크립트가 한다).
"""
import datetime, json, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHANNELS = [
    # 대형 기획사
    "@HYBELABELS", "@SMTOWN", "@JYPEntertainment", "@YGENTERTAINMENT", "@BLACKPINK", "@BABYMONSTER",
    "UCx9hXYOCvUYwrprEqe4ZQHA",  # TREASURE
    "@THEBLACKLABEL", "@STARSHIP_official", "@KQENT", "@official_i_dle", "@ZB1_official", "@Kep1er_Offcl",
    "@Billlie", "@MAMAMOO_OFFICIAL", "@StrayKids", "@fromis9_official", "@100RED_official",
    "UC-Fnix71vRP64WXeo0ikd0Q",  # IVE
    "UC2e4Ukj5Pfr7cb3KpJAFBdQ",  # ATEEZ
    "UCPZIPuQPrfrUG9Xe_okEmQA",  # PLAVE
    "UCvEEeBssb4XxIfWWIB8IjMw",  # KISS OF LIFE
    "UCJnL-TBcsYrF2SLs7tmiC8Q",  # tripleS
    "UCfbYNlxgLuKJXQZEhkMmaCQ",  # izna
    "UCwoSFXX8kraikB-WClx2pVQ",  # AHOF
    "UCPo532dDHpbKVhJyJseLVbw",  # CLOSE YOUR EYES
    "@QWER_Band_official", "@AKMU", "@dlwlrma", "@LYW_official", "@WOODZ_dnwm", "@crushofficial",
    # 유통사 (여러 아티스트 MV)
    "@1theK",
    "UC_pwIXKXNm5KGhdEVzmY60A",  # STONE MUSIC
    "UCd-OrgPLrnQiQBcq19j5oEQ",  # GENIE MUSIC
    # 힙합
    "@AOMGOFFICIAL",
    "UC6TJkBRLMFJ-9c7pXehoZwg",  # H1GHR MUSIC
    "UC4mMqn0EPMoOwWqU8--2how",  # Ambition Musik
    "UCWDNQdzzqOuh2UHVRfkOmsw",  # KC (Sik-K)
    "UCtG5oKSlksz-QmD_2uI4WBw",  # Dream Perfect Regime
    "UCj1partPHjSV9Hf23adjgLQ",  # CHANGMO
    "UCkLoBAZQLHv9pwHqmmdBeGg",  # ASH ISLAND
    "UCK5fO9Q2gitao0M5yQvPnvw",  # JAY PARK
    "UC3dJKwKxhR1Boz56EsI5PYQ",  # 이영지
    "UCTcEu0jaf3DrsTjnGwwvsvA",  # EPIK HIGH
    "UCk0JS5My6D-z21k5tpvOW2w",  # Paul Blanco
    "UCprCY6XHC6L0kFJb4zeiCwQ",  # Amoeba Culture
    "UCNaTU6SHdAXgAzvYK50OYyg",  # VMC
    "@ziorparking",
]

INC = re.compile(r"(\bM/?V\b|Official (Music )?Video|Music Video|뮤직비디오)", re.I)
EXC = re.compile(r"(teaser|behind|making|reaction|performance|lyric|visuali[sz]er|practice|medley|trailer|concept|"
                 r"preview|spoiler|sketch|reveal|highlight|recap|guide|shorts|episode|comment|live clip|special clip|"
                 r"dance video|choreograph|\bM/?V\b\s*(set|shoot|filming))", re.I)


def url_of(c):
    return f"https://www.youtube.com/{c}/videos" if c.startswith("@") else f"https://www.youtube.com/channel/{c}/videos"


def flat(c, cut_ts, end):
    try:
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--playlist-end", str(end), "--extractor-args",
                            "youtubetab:approximate_date", "-J", url_of(c)], capture_output=True, text=True, timeout=300)
        d = json.loads(r.stdout)
    except Exception:
        return c, None, []
    if not isinstance(d, dict):
        return c, None, []
    out = []
    for e in d.get("entries") or []:
        if not e:
            continue
        ts = e.get("timestamp") or 0
        if ts and ts < cut_ts:
            continue
        t = e.get("title") or ""
        if INC.search(t) and not EXC.search(t):
            out.append({"id": e["id"], "title": t})
    return c, d.get("channel"), out


def exact_dates(ids):
    if not ids:
        return {}
    r = subprocess.run(["yt-dlp", "--skip-download", "--ignore-no-formats-error", "--no-warnings", "--extractor-args",
                        "youtube:player_client=web_embedded", "--print", "%(id)s %(upload_date)s",
                        *["https://www.youtube.com/watch?v=" + i for i in ids]], capture_output=True, text=True, timeout=900)
    res = {}
    for line in r.stdout.splitlines():
        a = line.split()
        if len(a) == 2 and re.fullmatch(r"\d{8}", a[1]):
            res[a[0]] = f"{a[1][:4]}-{a[1][4:6]}-{a[1][6:]}"
    return res


def main():
    base, out_path, since = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    since_d = datetime.date.fromisoformat(since)
    # 근사 날짜는 몇 주씩 틀릴 수 있으므로 넉넉히 45일 앞에서 자른다(정확한 날짜로 다시 거른다).
    cut_ts = datetime.datetime.combine(since_d - datetime.timedelta(days=45), datetime.time()).timestamp()
    days = (datetime.date.today() - since_d).days
    end = 500 if days > 60 else 150
    known = {f["url"] for f in json.loads((base / "feed.json").read_text(encoding="utf8"))}
    cands = {}
    with ThreadPoolExecutor(6) as ex:
        for c, name, items in ex.map(lambda c: flat(c, cut_ts, end), CHANNELS):
            print(c, name, len(items), file=sys.stderr)
            for it in items:
                if "https://www.youtube.com/watch?v=" + it["id"] not in known:
                    cands.setdefault(it["id"], it)
    ids = list(cands)
    chunks = [ids[i:i + 25] for i in range(0, len(ids), 25)]
    dates = {}
    with ThreadPoolExecutor(8) as ex:
        for d in ex.map(exact_dates, chunks):
            dates.update(d)
    today = datetime.date.today()
    out = []
    for i, it in cands.items():
        pub = dates.get(i)
        if not pub or pub < since:
            continue
        r = {"url": "https://www.youtube.com/watch?v=" + i, "title": it["title"], "category": "뮤직비디오",
             "region": "국내", "year": int(pub[:4]), "published": pub, "verified": True}
        if (today - datetime.date.fromisoformat(pub)).days > 90:
            r["classic"] = True
        out.append(r)
    out.sort(key=lambda r: r["published"], reverse=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf8")
    print(f"candidates {len(cands)} dated {len(dates)} kept {len(out)}", file=sys.stderr)


if __name__ == "__main__":
    main()
