# -*- coding: utf-8 -*-
"""쇼츠 채널 조사 — 키워드 검색으로 후보 채널을 모으고, 채널마다 최근 쇼츠 조회수를 재서 표로 낸다(읽기만).

    python tools/channel_scan.py search <출력.json> "<키워드1>" "<키워드2>" ... [--n 60]
    python tools/channel_scan.py measure <후보.json> <출력.json> [--top 25] [--recent 30]

- search : yt-dlp ytsearch 로 키워드마다 영상 n개(제목·조회수·채널·길이)를 모은다. 60초 이하만 쇼츠 후보로 센다.
- measure: search 결과에서 채널을 모아(쇼츠 후보 조회수 합 순) 상위 top 개 채널의 /shorts 탭 최근 recent 개 조회수를 잰다
           → 중앙값·평균·10만 넘은 비율·구독자 수. 업로드 날짜는 flat 목록에 없어서 «최근 순서 recent 개» 기준이다.
의존: yt-dlp(PATH). 403·봇 차단은 우회하지 않는다 — 실패한 채널은 «측정 실패»로 남긴다.
"""
import json
import statistics
import subprocess
import sys


def run(args, timeout=300):
    p = subprocess.run(["yt-dlp", "--no-warnings", *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return p.stdout


def search(out, keywords, n):
    rows = []
    for kw in keywords:
        txt = run(["--flat-playlist", "-J", f"ytsearch{n}:{kw}"])
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            print("검색 실패:", kw)
            continue
        for e in data.get("entries") or []:
            rows.append({"kw": kw, "id": e.get("id"), "title": e.get("title"), "views": e.get("view_count"),
                         "dur": e.get("duration"), "channel": e.get("channel"), "channel_id": e.get("channel_id"),
                         "channel_url": e.get("channel_url")})
        print(kw, len(data.get("entries") or []))
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def measure(src, out, top, recent):
    rows = json.load(open(src, encoding="utf-8"))
    agg = {}
    for r in rows:
        if not r.get("channel_id") or not r.get("dur") or r["dur"] > 60:
            continue
        a = agg.setdefault(r["channel_id"], {"channel": r["channel"], "hits": 0, "views": 0, "kws": set(), "samples": []})
        a["hits"] += 1
        a["views"] += r.get("views") or 0
        a["kws"].add(r["kw"])
        a["samples"].append(r["title"])
    cand = sorted(agg.items(), key=lambda x: -x[1]["views"])[:top]
    result = []
    for cid, a in cand:
        txt = run(["--flat-playlist", "-J", "-I", f"1:{recent}", f"https://www.youtube.com/channel/{cid}/shorts"])
        try:
            d = json.loads(txt)
        except json.JSONDecodeError:
            result.append({"channel": a["channel"], "channel_id": cid, "error": "측정 실패"})
            print("측정 실패", a["channel"])
            continue
        v = [e.get("view_count") or 0 for e in d.get("entries") or []]
        item = {"channel": a["channel"], "channel_id": cid, "subs": d.get("channel_follower_count"),
                "n": len(v), "median": statistics.median(v) if v else 0, "mean": int(statistics.mean(v)) if v else 0,
                "over100k": round(sum(x >= 100_000 for x in v) / len(v), 2) if v else 0,
                "top3": sorted(v, reverse=True)[:3], "search_hits": a["hits"], "kws": sorted(a["kws"]),
                "sample_titles": a["samples"][:3],
                "recent_titles": [e.get("title") for e in (d.get("entries") or [])[:5]]}
        result.append(item)
        print(f'{item["channel"]} | 구독 {item["subs"]} | 중앙 {item["median"]:,.0f} | 10만+ {item["over100k"]}')
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    opt = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    if pos[0] == "search":
        search(pos[1], pos[2:], opt("--n", 60))
    elif pos[0] == "measure":
        measure(pos[1], pos[2], opt("--top", 25), opt("--recent", 30))
