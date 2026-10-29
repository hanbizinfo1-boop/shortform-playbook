# -*- coding: utf-8 -*-
"""S7 2D 재현 설명 쇼츠 — 원본 초로 쓴 계획 JSON → 목소리 잇기 + Remotion props → 렌더.

    python tools/s7_prep.py <계획.json> [--still 출력초,...] [--no-render]

계획(원본 초): src, out, words(전사 words.json), layers, pieces[{in,out}], scenes[{from,to,bg,bgDepth,bg2,cam,items}], captions[{from,to,text}]
  scenes 안 모든 시각(t0·t1·keys·poses·count·level·bg2.t0·cam)은 **원본 초** — 여기서 장면 안 초로 바꾼다.
  cam 의 t 만 장면 안 초(카메라는 말과 무관).
말 조각(10-29 «말 엄청끊김 … 뒷부분 끊기는 현상심함»):
  · 조각 끝 말이 문장 끝(-요·-다·-죠·-까·-네)이 아니면 ERROR
  · 자르는 점은 단어 끝~다음 단어 시작 사이 10ms RMS 최저점(꼬리 잘림 방지), 이음 15ms 녹임
렌더: tools/remotion2d (public/<작업>/ 에 레이어 _cut·목소리·글꼴 복사 → props.json → npx remotion render)
"""
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s6_render as s6  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RM = ROOT / "tools" / "remotion2d"
END_OK = ("요", "다", "죠", "까", "네", "요.", "다.", "죠.", "까?", "요?")


def load_words(p):
    ws = []
    for seg in json.loads(Path(p).read_text(encoding="utf-8")):
        ws += seg["words"]
    return ws


def rms_min(wav, a, b):
    """wav(16k 모노) 의 [a,b] 구간에서 10ms RMS 가 가장 낮은 시각."""
    sr, x = wav
    i0, i1 = int(a * sr), int(b * sr)
    if i1 - i0 < 320:
        return (a + b) / 2
    seg = x[i0:i1].astype(np.float32)
    hop = sr // 100
    e = [np.sqrt(np.mean(seg[k:k + hop] ** 2)) for k in range(0, len(seg) - hop, hop)]
    return a + int(np.argmin(e)) * hop / sr + hop / 2 / sr


def refine(pieces, words, wav):
    out, errs = [], []
    for p in pieces:
        inside = [w for w in words if w["s"] >= p["in"] - 0.15 and w["e"] <= p["out"] + 0.15]
        first, last = inside[0], inside[-1]
        prev = max((w for w in words if w["e"] <= first["s"] + 1e-3 and w is not first), key=lambda w: w["e"], default=None)
        nxt = min((w for w in words if w["s"] >= last["e"] - 1e-3 and w is not last), key=lambda w: w["s"], default=None)
        a = rms_min(wav, max(prev["s"], first["s"] - 0.4), first["s"] + 0.08) if prev else max(first["s"] - 0.15, 0)   # 전사 단어 경계는 붙어 있어 앞뒤로 넓혀 찾는다
        b = rms_min(wav, last["e"] - 0.08, min(nxt["e"], last["e"] + 0.4)) if nxt else last["e"] + 0.2
        tail = re.sub(r"[^가-힣?.!]", "", last["w"])
        if not tail.endswith(END_OK):
            errs.append(f"ERROR 조각 끝이 문장 끝이 아님: «{last['w'].strip()}» @ {last['e']:.2f} (10-29 «하다말아»)")
        out.append({"in": round(a, 3), "out": round(b, 3), "words": f"{first['w'].strip()} … {last['w'].strip()}"})
    return out, errs


def white_rect(p):
    """그림 안 가장 큰 흰 화면(>242) 사각형 → (정규화 x,y,w,h), (폭, 높이). 폰·노트북·모니터 화면에 UI 를 얹는 자리."""
    import cv2
    from PIL import Image
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im)
    m = ((a[..., :3].min(axis=2) > 242) & (a[..., 3] > 200)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 4)
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = st[i, :4]
    W_, H_ = im.size
    return [round(x / W_, 4), round(y / H_, 4), round(w / W_, 4), round(h / H_, 4)], [W_, H_]


def char_rows(text, rows):
    """자막 글자 위치 → 정렬 행 번호(align_chars 토큰 규칙 그대로: 한글 음절 1 · 숫자/영문 덩어리 1)."""
    idx, k, pos = {}, 0, 0
    for word in text.split(" "):
        prev_unk = False
        for ch in word:
            if "가" <= ch <= "힣":
                idx[pos] = k; k += 1; prev_unk = False
            elif ch.isalnum() and not prev_unk:
                idx[pos] = k; k += 1; prev_unk = True
            elif ch.isalnum():
                idx[pos] = k - 1
            pos += 1
        pos += 1
    return idx


def align_pieces(src, pieces, caps, words, wav):
    """조각마다 앞말·자막들·뒷말을 강제 정렬 → 말 시작·끝, 앞뒤 쉼, 자막 시각. 말끊김 검사(10-29 «검사기넣어서 문제있으면 무조건 반려»)."""
    from align_chars import align
    sr, x = wav
    hop = sr // 100
    allx = x.astype(np.float32)
    def lvl(a, b):
        seg = allx[int(a * sr):int(b * sr)]
        e = [np.sqrt(np.mean(seg[k:k + hop] ** 2)) + 1 for k in range(0, max(len(seg) - hop, 1), hop)]
        return 20 * np.log10(np.array(e))
    out, errs, capt = [], [], []
    for p in pieces:
        cs = [c for c in caps if p["in"] - 0.3 <= c["from"] < p["out"]]
        a, b = p["in"] - 2.5, p["out"] + 2.5
        prev = " ".join(w["w"].strip() for w in words if a + 0.3 <= w["s"] and w["e"] <= p["in"] + 0.05)
        nxt = " ".join(w["w"].strip() for w in words if p["out"] - 0.05 <= w["s"] and w["e"] <= b - 0.3)
        rows = align(src, a, b, [prev] + [c["text"] for c in cs] + [nxt])
        s0 = rows[1][0][1]
        e0 = rows[-2][-1][2]
        pe = rows[0][-1][2] if rows[0] else a
        ns = rows[-1][0][1] if rows[-1] else b
        speech = lvl(s0, e0)
        ref = np.percentile(speech, 90)
        # 자르는 점 = 앞말 끝~말 시작 / 말 끝~뒷말 시작 사이 최저 음량
        cin = rms_min(wav, pe, s0 + 0.02) if rows[0] else s0 - 0.12
        cout = rms_min(wav, max(e0 - 0.02, s0), ns) if rows[-1] else e0 + 0.25
        for name, t, gap in (("시작", cin, s0 - pe), ("끝", cout, ns - e0)):
            here = lvl(t - 0.015, t + 0.015).max()
            if here > ref - 18:
                errs.append(f"ERROR 말끊김({name}) @ {t:.2f}: 자르는 점 소리 {here - ref:+.1f}dB(말 대비) — 쉼이 없는 자리(앞뒤 틈 {gap:.2f}초)")
        tail = re.sub(r"[^가-힣?.!]", "", cs[-1]["text"].split()[-1]) if cs else ""
        if not p.get("end_ok") and not tail.endswith(END_OK):
            errs.append(f"ERROR 조각 끝이 문장 끝이 아님: «{cs[-1]['text']}» (10-29 «하다말아»)")
        out.append({"in": round(cin, 3), "out": round(cout, 3), "words": f"{cs[0]['text'][:8]} … {cs[-1]['text'][-8:]}"})
        for i, c in enumerate(cs):
            r = rows[1 + i]
            st = r[0][1] if r else c["from"]
            en = rows[2 + i][0][1] if i + 1 < len(cs) and rows[2 + i] else cout
            capt.append({"text": c["text"], "from": max(st - 0.05, cin), "to": en - 0.02 if i + 1 < len(cs) else cout, "rows": r, "map": char_rows(c["text"], r)})
    return out, errs, capt


def beat_time(v, capt, lo=-1.0):
    """박자: 숫자(원본 초) 또는 «자막 속 낱말[@n][+초]» — 그 낱말 첫 음절이 소리 나는 시각(강제 정렬)."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"^(.*?)(?:@(\d+))?([+-]\d*\.?\d+)?$", v)
    word, nth, off = m.group(1), int(m.group(2) or 1), float(m.group(3) or 0)
    seen = 0
    for c in capt:
        if c["to"] <= lo:   # 샷 시작보다 앞 자막은 건너뜀(같은 낱말이 후킹에도 나올 때 — 10-29 «한 달에»)
            continue
        i = c["text"].find(word)
        while i >= 0:
            seen += 1
            if seen == nth:
                k = c["map"].get(i)
                if k is None or k >= len(c["rows"]):
                    raise ValueError(f"박자 «{v}» 정렬 못 함")
                return c["rows"][k][1] + off
            i = c["text"].find(word, i + 1)
    if lo > -1:   # 샷 시작 뒤에 없으면(앞에서 이미 쌓인 줄 — 마지막 통장 샷) 처음부터 다시 찾는다
        return beat_time(v, capt)
    raise ValueError(f"박자 «{v}» 자막에 없음")


def read_wav(p):
    with wave.open(str(p)) as f:
        sr = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), np.int16)
    return sr, x


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    plan = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    still = [float(x) for x in a[a.index("--still") + 1].split(",")] if "--still" in a else None
    words = load_words(ROOT / plan["words"])
    # 목소리 원천: 원본에 배경음악이 깔린 구간이 있으면 자를 때 음악도 끊긴다 → demucs 로 뽑은 목소리(plan "voice")를 쓴다
    vsrc = str(ROOT / plan["voice"]) if plan.get("voice") else plan["src"]
    wav16 = ROOT / plan.get("wav16", "_tmp/빡이사신규/audio.wav")
    if plan.get("voice"):
        wav16 = ROOT / "_tmp" / "s7" / (Path(plan["voice"]).stem + "_16k.wav")
        if not wav16.exists():
            wav16.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vsrc, "-ac", "1", "-ar", "16000", str(wav16)], check=True)
    if plan.get("align", True):
        pieces, errs, capt = align_pieces(vsrc, plan["pieces"], plan["captions"], words, read_wav(wav16))
    else:
        (pieces, errs), capt = refine(plan["pieces"], words, read_wav(wav16)), None
    for p in pieces:
        print(f"조각 {p['in']:.3f}–{p['out']:.3f}  {p['words']}")
    for e in errs:
        print(e)
    if errs and "--force" not in a:
        print("반려 — ERROR 가 있으면 렌더하지 않는다(10-29 «문제있으면 무조건 반려»). 조각을 고친 뒤 다시.")
        sys.exit(2)
    B = (lambda v: beat_time(v, capt)) if capt else float

    def to_out(s):
        acc = 0.0
        for p in pieces:
            if p["in"] - 0.3 <= s <= p["out"] + 0.3:
                return acc + min(max(s - p["in"], 0), p["out"] - p["in"])
            acc += p["out"] - p["in"]
        raise ValueError(f"조각 밖 시각 {s}")
    total = sum(p["out"] - p["in"] for p in pieces)

    job = Path(plan["out"]).name
    pub = RM / "public" / job
    pub.mkdir(parents=True, exist_ok=True)
    (RM / "public" / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "소재" / "fonts" / "Pretendard-Bold.otf", RM / "public" / "fonts" / "Pretendard-Bold.otf")
    layers = ROOT / plan["layers"]
    used = set()

    def asset(name):
        src = layers / name
        cut = src.with_name(src.stem + "_cut.png")
        src = cut if cut.exists() else src
        shutil.copy(src, pub / name)
        used.add(name)
        return f"{job}/{name}"

    # 목소리
    voice = pub / "voice.wav"
    fl = ";".join(f"[0:a]atrim={p['in']}:{p['out']},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:st={p['out'] - p['in'] - 0.015:.3f}:d=0.015[a{i}]" for i, p in enumerate(pieces))
    fl += ";" + "".join(f"[a{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vsrc, "-filter_complex", fl, "-map", "[v]", "-ar", "48000", "-ac", "2", str(voice)], check=True)

    for fn in ("Pretendard-ExtraBold.otf", "Pretendard-Black.otf"):
        shutil.copy(ROOT / "소재" / "fonts" / fn, RM / "public" / "fonts" / fn)
    comp = "Shots" if "shots" in plan else "Shorts2D"
    shots = []
    for sh in plan.get("shots", []):
        def edge(v):  # 샷 경계: «^n»/«$n» = n번째 조각 시작/끝, 글자 = 그 낱말 소리 시작, 숫자 = 원본 초
            if isinstance(v, str) and v[:1] in "^$" and v[1:].isdigit():
                pc = pieces[int(v[1:]) - 1]
                return pc["in"] if v[0] == "^" else pc["out"]
            return B(v)
        src0 = edge(sh["from"])
        s0, s1 = to_out(src0), to_out(edge(sh["to"]))
        Bs = (lambda v, lo=src0 - 0.05: beat_time(v, capt, lo)) if capt else float
        L = lambda t: round(to_out(t) - s0, 4)  # noqa: E731  원본 초 → 샷 안 초
        o = {"type": sh["type"], "start": s0, "end": s1, "beats": {k: L(Bs(v)) for k, v in sh.get("beats", {}).items()},
             "img": {k: asset(f) for k, f in sh.get("img", {}).items()}, "p": dict(sh.get("p", {})), "scr": {}, "size": {}}
        if "cups" in o["p"]:
            o["p"]["cups"] = [[x, y, L(Bs(ts))] for x, y, ts in o["p"]["cups"]]
        if "taps" in o["p"]:
            o["p"]["taps"] = [L(Bs(ts)) for ts in o["p"]["taps"]]
        for k in sh.get("screens", []):
            o["scr"][k], o["size"][k] = white_rect(pub / sh["img"][k])   # 복사된(_cut) 그림 기준
        shots.append(o)
    scenes = []
    for sc in plan.get("scenes", []):
        s0, s1 = to_out(sc["from"]), to_out(sc["to"])
        base = sc["from"]
        L = lambda t: round(to_out(t) - s0, 4) if t > 0.0 else t   # noqa: E731  원본 초 → 장면 안 초
        o = {"start": s0, "end": s1, "bgDepth": sc.get("bgDepth", 0.4), "cam": sc.get("cam"), "items": []}
        if sc.get("bg"):
            o["bg"] = asset(sc["bg"])
        if sc.get("bg2"):
            o["bg2"] = {"file": asset(sc["bg2"]["file"]), "t0": L(sc["bg2"]["t0"]), "dur": sc["bg2"]["dur"]}
        for it in sc["items"]:
            it = dict(it)
            for k in ("t0", "t1"):
                if k in it:
                    it[k] = L(it[k])
            if "keys" in it:
                it["keys"] = [[L(t), v] for t, v in it["keys"]]
            if "poses" in it:
                it["poses"] = [[L(t), asset(f)] for t, f in it["poses"]]
            if "count" in it:
                it["count"] = [[L(t), n] for t, n in it["count"]]
            if "level" in it:
                it["level"] = [[L(t), v] for t, v in it["level"]]
            if "file" in it:
                it["file"] = asset(it["file"])
            o["items"].append(it)
        scenes.append(o)
        _ = base
    s6.SRC_FOR_SPLIT[:] = [vsrc]
    caps = []
    for c in (capt or plan["captions"]):
        for p in s6.split_caption({"from": c["from"], "to": c["to"], "text": c["text"]}):
            caps.append({"start": round(to_out(p["from"]), 3), "end": round(to_out(p["to"]), 3), "text": p["text"]})
    props = {"fps": plan.get("fps", 30), "duration": round(total, 3), "voice": f"{job}/voice.wav", "scenes": scenes, "shots": shots, "captions": caps}
    if plan.get("title"):
        props["title"] = plan["title"]
        props["brush"] = asset(plan.get("brush", "brush_band.png"))
    if plan.get("grade"):
        props["grade"] = [round(to_out(plan["grade"][0]), 3), round(to_out(plan["grade"][1]), 3)]
    pp = pub / "props.json"
    pp.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    out = ROOT / plan["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_suffix(".srt"), "w", encoding="utf-8", newline="\n") as f:
        for k, c in enumerate(caps, 1):
            f.write(f"{k}\n{srt(c['start'])} --> {srt(c['end'])}\n{c['text']}\n\n")
    print(f"props {pp} · 길이 {total:.2f}초 · 자막 {len(caps)} · 레이어 {len(used)}")
    if "--no-render" in a:
        return
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    if still:
        for t in still:
            dst = out.with_name(out.name + f"_{t:05.2f}s.png")
            subprocess.run([npx, "remotion", "still", "src/index.ts", comp, str(dst), f"--props={pp}", f"--frame={int(round(t * props['fps']))}", "--log=error"], cwd=RM, check=True)
            print("정지", dst)
        return
    subprocess.run([npx, "remotion", "render", "src/index.ts", comp, str(out.with_suffix(".mp4")), f"--props={pp}",
                    "--codec=h264", "--crf=18", "--concurrency=4", "--log=error"], cwd=RM, check=True)
    keep = ROOT / "_tmp" / "s7" / f"{job}_무음효과.mp4"   # s7_sfx 가 이 판에 효과음을 섞는다
    keep.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(out.with_suffix(".mp4"), keep)
    print("완료", out.with_suffix(".mp4"), f"{total:.1f}초", "· ERROR", len(errs))


def srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


if __name__ == "__main__":
    main()
