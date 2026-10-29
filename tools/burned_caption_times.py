# -*- coding: utf-8 -*-
"""롱폼에 구워진 자막이 «바뀌는 순간»을 프레임 차이로 잰다 — 자막 정본(사람이 손본 글)의 시각을 얻는 용도.

    python tools/burned_caption_times.py <영상> <시작초> <끝초> [--band x0,y0,x1,y1] [--fps 30] [--thr 6]

band: 자막 띠 영역(원본 픽셀, 기본 1920×1080 롱폼의 아래 가운데 560,900,1360,1010).
출력: 자막 구간 목록 «시작 끝 (밝은 글자 비율)» — 글자가 없는 구간(비율 0 근처)은 «없음».
글은 접촉 시트로 사람이 읽어서 순서대로 짝짓는다(OCR 없음).
"""
import subprocess
import sys

import numpy as np


def frames(src, t0, t1, band, fps):
    x0, y0, x1, y1 = band
    w, h = x1 - x0, y1 - y0
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", src,
           "-vf", f"fps={fps},crop={w}:{h}:{x0}:{y0},format=gray", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(w * h)
        if len(buf) < w * h:
            break
        yield t0 + n / fps, np.frombuffer(buf, np.uint8).reshape(h, w).astype(np.int16)
        n += 1


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    src, t0, t1 = a[0], float(a[1]), float(a[2])
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    band = [int(v) for v in opt("--band", "560,900,1360,1010").split(",")]
    fps, thr = float(opt("--fps", "30")), float(opt("--thr", "6"))
    segs, start, prev, ink = [], None, None, []
    for t, f in frames(src, t0, t1, band, fps):
        bright = float((f > 225).mean())  # 흰 글자 비율
        if prev is not None and np.abs(f - prev).mean() > thr:
            if start is not None:
                segs.append((start, t, float(np.median(ink))))
            start, ink = t, []
        if start is None:
            start = t
        ink.append(bright)
        prev = f
    segs.append((start, t1, float(np.median(ink)) if ink else 0))
    for s, e, b in segs:
        tag = "없음" if b < 0.004 else f"{b:.3f}"
        print(f"{s:8.2f} {e:8.2f}  {e - s:5.2f}s  {tag}")


if __name__ == "__main__":
    main()
