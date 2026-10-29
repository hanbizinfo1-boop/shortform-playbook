# -*- coding: utf-8 -*-
"""Codex 레이어 그림 → 깨끗한 오려 낸 PNG(<이름>_cut.png). anim2d 가 _cut 을 먼저 쓴다.

    python tools/layer_cut.py <레이어폴더> [파일 ...]      # 파일을 안 주면 bg_* 를 뺀 전부

- RGBA(Codex 가 투명 배경으로 준 것): 테두리에 흐린 빛 번짐(알파 일부)이 붙어 온다 → 진한 알파(>200) 덩어리의 구멍을 메운
  윤곽 안쪽만 남기고 밖은 0(유리처럼 안쪽 반투명은 그대로). 윤곽 1px 깎고 1px 녹임.
- RGB(흰 바탕): 테두리와 이어진 거의 흰색(>242)을 바탕으로 보고 지움(옷 안쪽 흰색은 윤곽선에 막혀 남음).
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def fill_holes(m):
    h, w = m.shape
    ff = m.copy().astype(np.uint8) * 255
    pad = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, pad, (0, 0), 128)
    return (ff != 128)


def cut(p):
    im = Image.open(p)
    if im.mode == "RGBA":
        rgba = np.asarray(im).copy()
        a = rgba[..., 3]
        core = a > 200
        n, lab, stats, _ = cv2.connectedComponentsWithStats(core.astype(np.uint8), 8)
        keep = np.zeros_like(core)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] > 400:
                keep |= lab == i
        sil = fill_holes(cv2.morphologyEx(keep.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)) > 0)
    else:
        rgb = np.asarray(im.convert("RGB")).copy()
        white = (rgb.min(axis=2) > 242).astype(np.uint8)
        h, w = white.shape
        bgm = np.zeros((h + 2, w + 2), np.uint8)
        ff = white.copy()
        for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            if ff[y, x] == 1:
                cv2.floodFill(ff, bgm, (x, y), 2)
        sil = ff != 2
        rgba = np.dstack([rgb, np.full((h, w), 255, np.uint8)])
        a = rgba[..., 3]
    sil = cv2.erode(sil.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    soft = cv2.GaussianBlur(sil.astype(np.float32), (3, 3), 0)
    rgba[..., 3] = (np.minimum(a.astype(np.float32) / 255, soft) * 255).astype(np.uint8)
    ys, xs = np.where(rgba[..., 3] > 8)
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = p.with_name(p.stem + "_cut.png")
    Image.fromarray(rgba).save(out)
    print("오림", out.name, rgba.shape[1], "x", rgba.shape[0])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d = Path(sys.argv[1])
    fs = [d / f for f in sys.argv[2:]] or [p for p in sorted(d.glob("*.png")) if not p.stem.startswith("bg_") and not p.stem.endswith("_cut")]
    for p in fs:
        cut(p)
