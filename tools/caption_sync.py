# -*- coding: utf-8 -*-
"""자막 ↔ 목소리 싱크 재기·맞추기 (10-14 사장님 «자막이랑 목소리 나오는 타이밍 정확도도 너무낮은데»).

계획 captions 의 글자를 전사 단어(words.json)의 글자 흐름에 맞대어(글자 단위 정렬) 각 자막의
첫 글자가 실제로 소리 나는 시각·끝 글자가 끝나는 시각을 찾는다.
  measure(plan) → [{i, text, from, to, v_from, v_to, d_from, d_to, cover}]
  python tools/caption_sync.py <plan.json>          → 어긋남 표
  python tools/caption_sync.py <plan.json> --fix    → 자막 from/to 를 목소리 시각으로 고쳐 같은 파일에 저장
  python tools/caption_sync.py <plan.json> --exact  → 모든 자막 시작·끝을 강제 정렬 음절 시각 그대로(10-16 06편 «SRT정합성이 너무 안맞는데»)
    --fix 는 «늦은 자막만, 0.5초 안»만 당겨 이른 자막(전사 시각으로 적은 계획)·끝 시각이 그대로 남았다
"""
import difflib
import json
import re
import sys

KEEP = re.compile(r"[0-9A-Za-z가-힣]")


def _chars(text):
    return [ch for ch in text if KEEP.match(ch)]


def word_stream(words_path, t0, t1):
    """t0~t1 의 전사 글자 흐름: [(글자, 시작, 끝)] — 단어 시간을 글자 수로 고르게 나눈다."""
    segs = json.load(open(words_path, encoding="utf-8"))
    out = []
    for sg in segs:
        if sg["end"] < t0 or sg["start"] > t1:
            continue
        for w in sg.get("words", []):
            if w["e"] < t0 or w["s"] > t1:
                continue
            cs = _chars(w["w"])
            n = max(len(cs), 1)
            for k, ch in enumerate(cs):
                out.append((ch, w["s"] + (w["e"] - w["s"]) * k / n, w["s"] + (w["e"] - w["s"]) * (k + 1) / n))
    return out


def rms10(path, t0, t1, sr=16000):
    """t0~t1 음량(dB) 10ms 간격 → (시작초, 배열)."""
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", path,
                          "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(float) / 32768
    win = sr // 100
    n = len(x) // win
    x = x[:n * win].reshape(n, win)
    return t0, 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-9)


def onsets(t0, db, quiet=-35, loud=-28, min_gap=0.05):
    """쉼(quiet 아래 min_gap 이상) 다음 첫소리(loud 위) 시각들. 전사 단어 시각은 앞 숨까지 먹어 0.2~0.6초 이를 때가 있어
    (10-14 실측: 1620.80 «라고» 전사 1620.14 / 실제 1620.85) 자막 시작은 이 실제 소리 시각으로 잡는다."""
    out, run = [], 0
    k = int(min_gap * 100)
    for i, v in enumerate(db):
        if v < quiet:
            run += 1
        else:
            if v > loud and run >= k:
                out.append(t0 + i / 100)
            if v > loud:
                run = 0
    return out


def voice_start(v_from, cap_from, ons):
    """자막 하나의 실제 목소리 시작.
    ① 전사 시작(v_from) 근처(−0.1~+0.4) 실제 첫소리(쉼 다음) — 전사는 앞 숨을 먹어 이르게 찍히곤 해 +0.1 쪽 우선
    ② 없으면 지금 자막 시각 ±0.2 의 실제 첫소리 ③ 둘 다 없으면(쉼 없이 이어 말함) 전사 + 0.08
    (10-14: 앞 판은 «지금 자막 근처 첫소리»를 먼저 골라 늦은 자막을 그대로 인정했다 — 01편 «그런데 광고는요» 0.25초 늦음)"""
    if v_from is not None:
        near = [o for o in ons if v_from - 0.1 <= o <= v_from + 0.4]
        if near:
            return min(near, key=lambda o: abs(o - v_from - 0.1)), "쉼"
    near = [o for o in ons if cap_from - 0.2 <= o <= cap_from + 0.2]
    if near:          # 전사 근처엔 쉼이 없고 지금 자막 자리에 쉼이 있으면 그쪽(전사가 이어 말하는 중간에 찍힌 것 — 04편 446.37)
        return min(near, key=lambda o: abs(o - cap_from)), "쉼"
    if v_from is not None:
        return v_from + 0.08, "전사"
    return cap_from, "없음"


def measure(plan):
    """조각마다 그 조각 자막 글자를 원본 소리에 강제 정렬(align_chars) → 자막 첫 음절이 소리 나는 시각.
    (10-14: 전사 단어 시각·음량 쉼으로 재던 앞 판은 경계를 0.3~0.6초씩 잘못 짚었다 — 정렬로 판정하니 원 자막이 맞았던 곳이 많음)"""
    from align_chars import align
    caps = plan["captions"]
    res = []
    for p in plan["pieces"]:
        pc = [(i, c) for i, c in enumerate(caps) if p["in"] - 0.5 <= c["from"] < p["out"]]
        if not pc:
            continue
        rows = align(plan["src"], max(p["in"] - 0.3, 0), p["out"] + 0.3, [c["text"] for i, c in pc])
        for (i, c), row in zip(pc, rows):
            r = {"i": i, "text": c["text"], "from": c["from"], "to": c["to"], "first": abs(c["from"] - p["in"]) < 0.05,
                 "cover": 1.0 if row else 0.0}
            if row:
                # 숫자·영문으로 시작하면(«#» 덩어리) 정렬 시각이 구간 잡기에 따라 흔들린다(01편 «65세» 824.61↔825.04) → 판정·이동 안 함
                r["v_from"], r["v_to"], r["how"] = row[0][1], row[-1][2], ("숫자" if row[0][0] == "#" else "정렬")
            else:
                r["v_from"], r["v_to"], r["how"] = c["from"], c["to"], "없음"
            r["d_from"] = c["from"] - r["v_from"]
            r["d_to"] = c["to"] - r["v_to"]
            res.append(r)
    return res


def fix(plan, res):
    """늦게 뜨는 자막만 당긴다: 시작 = 목소리 시작(앞으로만, 0.6초 안). 앞 자막 끝도 같이 당겨 이어지게.
    그 자막 시각에 묶어 둔 확대·표시·효과음 키도 같이 옮긴다(화면 변화가 자막과 따로 놀지 않게).
    조각 첫 자막은 조각 시작(in)보다 앞으로 가지 않는다. 맞춘 글자 60% 미만은 손대지 않는다."""
    caps = plan["captions"]
    moved = {}
    for r in res:
        if r["first"] or r["how"] in ("없음", "숫자"):
            continue
        c = caps[r["i"]]
        new = r["v_from"]
        if c["from"] - 0.8 <= new <= c["from"] + 0.5 and abs(new - c["from"]) >= 0.04:
            moved[c["from"]] = round(new, 2)
    for c in caps:
        if c["from"] in moved:
            c["from"] = moved[c["from"]]
        if c["to"] in moved:
            c["to"] = moved[c["to"]]

    def mv(t):
        return moved.get(t, t)
    for sh in plan.get("shots", []):
        for z in sh.get("zoom", []):
            z[0] = mv(z[0])
        for m in sh.get("marks", []):
            m["at"] = mv(m["at"])
        for ov in sh.get("overlays", []):
            if ov.get("from") is not None:
                ov["from"] = mv(ov["from"])
    for fx in plan.get("sfx", []):
        if isinstance(fx.get("at"), (int, float)):
            fx["at"] = mv(fx["at"])
    return plan


def exact(plan, res):
    """시작 = 첫 음절 시작(조각 in 보다 앞으로 안 감), 끝 = 다음 자막이 0.7초 안에 이어지면 그 시작, 아니면 끝 음절 + 0.2(조각 out 까지).
    화면 표시·효과음 키는 화면 변화에 묶여 있어 옮기지 않는다."""
    caps = plan["captions"]
    by = {r["i"]: r for r in res if r["how"] == "정렬"}
    piece = lambda c: next((p for p in plan["pieces"] if p["in"] - 0.5 <= c["from"] < p["out"]), None)
    order = sorted(by)
    for k, i in enumerate(order):
        c, r, p = caps[i], by[i], piece(caps[i])
        c["from"] = round(max(r["v_from"], p["in"]), 2)
        nxt = by.get(order[k + 1]) if k + 1 < len(order) else None
        if nxt and piece(caps[order[k + 1]]) is p and nxt["v_from"] - r["v_to"] < 0.7:
            c["to"] = round(nxt["v_from"], 2)
        else:
            c["to"] = round(min(r["v_to"] + 0.2, p["out"]), 2)
    return plan


def main():
    path = sys.argv[1]
    plan = json.load(open(path, encoding="utf-8"))
    res = measure(plan)
    bad = 0
    for r in res:
        flag = "ok" if r["first"] or r["how"] == "숫자" else ("XX" if r["d_from"] > 0.10 or r["d_from"] < -0.25 or r["cover"] < 0.6 else "ok")
        bad += flag == "XX"
        print(f"  {flag}  {r['from']:8.2f}  목소리 {r['v_from']:8.2f}({r['how']})  늦음 {r['d_from']:+.2f}s  "
              f"글자 {r['cover']:.0%}  «{r['text']}»")
    print(f"어긋남(첫 음절보다 0.10초↑ 늦게 / 0.25초↑ 이르게): {bad}/{len(res)}")
    if "--fix" in sys.argv:
        fix(plan, res)
        open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
        print("고침 →", path)
    elif "--exact" in sys.argv:
        exact(plan, res)
        open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
        print("정렬 시각 그대로 →", path)


if __name__ == "__main__":
    main()
