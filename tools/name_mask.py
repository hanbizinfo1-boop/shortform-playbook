# -*- coding: utf-8 -*-
"""원본 화면의 실제 업체명·전화번호를 찾아 계획 샷에 가림 상자(mask)를 넣는다 (CLAUDE.md 4 «업체명은 ○○»).

    python tools/name_mask.py <계획.json> [--step 0.1]

graphic·pan 샷마다 쓰는 원본 구간을 step 초 간격으로 OCR(easyocr ko, GPU) → s6_check.exposed_spans 로 판정 →
글자 위치를 비례로 잘라 «이름 부분만» 상자로(앞뒤 여유 8px) → 샷 "mask": [[x, y, w, h, from, to], ...] (원본 좌표·원본 초).
같은 자리에서 이어지는 시각은 하나로 묶는다. 렌더러가 그 시간 동안 흐림으로 가린다. 점검기 N 이 완성본을 다시 본다.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s6_check import exposed_spans  # noqa: E402


def frame(src, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3)


KNOWN = []   # 편과 상관없이 늘 가릴 이름(필요하면 추가)


def fuzzy_spans(tt, names):
    """이미 찾은 이름과 60% 이상 닮은 글자열 범위(앞뒤 1자 여유)."""
    import difflib
    out = []
    for n in names:
        L = len(n)
        for i in range(0, max(len(tt) - L + 2, 1)):
            for ln in (L - 1, L, L + 1):
                seg = tt[i:i + ln]
                if len(seg) >= max(L - 1, 2) and difflib.SequenceMatcher(None, seg, n).ratio() >= 0.6:
                    out.append((i, i + ln))
                    break
    return out


def frames(src, a, b, step):
    """a~b 를 한 번에 읽어 step 초 간격 프레임을 낸다(프레임마다 찾아 들어가면 10배 느림)."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src,
                          "-vf", f"fps={1 / step}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, i = 1920 * 1080 * 3, 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield a + i * step, np.frombuffer(buf, np.uint8).reshape(1080, 1920, 3)
        i += 1


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(sys.argv[1])
    step = float(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else 0.1
    plan = json.loads(path.read_text(encoding="utf-8"))
    import easyocr
    rd = easyocr.Reader(["ko", "en"], gpu=True, verbose=False)
    for sh in plan["shots"]:
        if sh["kind"] not in ("graphic", "pan"):
            continue
        spans = [(max(a["in"], sh["from"]), min(a["out"], sh["to"])) for a in plan["pieces"]
                 if a["out"] > sh["from"] and a["in"] < sh["to"]]
        found, seen = [], []
        for a, b in spans:
            prev, res = None, []
            for t, img in frames(plan["src"], a, b, step):
                small = img[::8, ::8].astype(np.int16)
                # 화면이 그대로면(화면녹화는 대부분 멈춰 있다) 앞 OCR 결과를 다시 쓴다 — 5~10배 빠름
                if prev is None or np.abs(small - prev).mean() > 0.4:
                    res = rd.readtext(img)
                    prev = small
                seen.append((t, res))
        # 1차: 규칙으로 이름 찾기 → 2차: 찾은 이름과 비슷한 글자열(선택 표시·흐림으로 잘못 읽힌 것)도 가린다
        #   (10-14 03편: 파란 선택 표시가 덮인 «○○캐피탈» 줄을 규칙이 놓쳐 1프레임 샘)
        names = set()
        for t, res in seen:
            for box, txt, conf in res:
                tt = txt.replace(" ", "")
                for s0, s1 in exposed_spans(tt):
                    names.add(tt[s0:s1])
        names |= set(KNOWN)
        for t, res in seen:
            for box, txt, conf in res:
                if conf < 0.1:
                    continue
                tt = txt.replace(" ", "")
                for s0, s1 in exposed_spans(tt) + fuzzy_spans(tt, names):
                        xs = [p[0] for p in box]
                        ys = [p[1] for p in box]
                        x0, x1 = min(xs), max(xs)
                        n = max(len(tt), 1)
                        bx0 = x0 + (x1 - x0) * s0 / n - 8
                        bx1 = x0 + (x1 - x0) * s1 / n + 8
                        found.append([int(bx0), int(min(ys) - 4), int(bx1 - bx0), int(max(ys) - min(ys) + 8),
                                      round(t, 2), tt[s0:s1]])  # noqa
        # 같은 자리(겹침) + 이어지는 시각은 하나로
        masks = []
        for x, y, w, h, t, name in sorted(found, key=lambda r: (r[4], r[0])):
            for m in masks:      # 거의 같은 자리(±6px)에서 이어지면 시간만 늘린다(스크롤 중엔 샘플마다 새 상자)
                if abs(m[0] - x) <= 6 and abs(m[1] - y) <= 6 and t - m[5] <= step * 1.5 + 0.01:
                    m[0], m[1] = min(m[0], x), min(m[1], y)
                    m[2], m[3] = max(m[2], w) + 6, max(m[3], h) + 6
                    m[5] = t
                    break
            else:
                masks.append([x, y, w, h, t, t, name])
        out = [[x, y, w, h, round(t0 - step * 1.6, 2), round(t1 + step * 1.6, 2)] for x, y, w, h, t0, t1, _ in masks]
        old = [m for m in sh.get("mask", []) if len(m) == 4]           # 손으로 넣은 고정 상자는 남긴다
        sh["mask"] = old + out
        names = sorted({m[6] for m in masks})
        if masks:
            print(f"  샷 {sh['from']}~{sh['to']}: 상자 {len(masks)}개 · {', '.join(names)}")
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("저장 →", path)


if __name__ == "__main__":
    main()
