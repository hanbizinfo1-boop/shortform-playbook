# -*- coding: utf-8 -*-
"""S6 «무대» 시안 — 전체 화면은 디자인한 무대, 롱폼 조각은 무대 위 도구(10-15 사장님
«전체적인화면은 블렌더나 에펙 클로드디자인 힉스필드등으로 구조를 잡아보자 롱폼에서 잘라서 쓰는건 오히려 도구처럼보고»
«2편에서 화면 키프레임이 한화면에서 되게 깔끔하게» «1편에서 왼쪽 상단에있던 4가지 단계를 끌고와서 하나의 화면에 넣은시도도 좋았는데»).

같은 순간(03편 «5월 29일에 게재 시작함», 원본 1949.5)을 무대 셋으로 — 고르시게 정지 시안만 만든다(영상 X).
  A 모니터 무대 + 화면 안 키프레임 확대(02편 방식) · B 다크 스튜디오 + 떠 있는 실제 화면 창(에펙 3D 층 느낌) · C 폰 무대 + 실제 카드 두 장을 피드처럼
공통: 위 1편식 단계 탭(현재 단계 강조), 아래 자막 A2. 무대 이미지 = Codex(`소재/ai/stage/`, 화면은 크로마 초록).

    python tools/scenes/stage_drafts.py      → 납품/빡이사DB_쇼츠/_무대시안/A·B·C.png
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from s6_render import title_bar, caption_img, font, FONT_XB, FONT_B, TOP, CAP_Y, W, H  # noqa: E402

SRC = "D:/26년 10월/261006/쇼츠자동화/빡이사DB.mp4"
STAGE = ROOT / "소재" / "ai" / "stage"
OUT = ROOT / "납품" / "빡이사DB_쇼츠" / "_무대시안"
T = 1948.0          # 1949.5 는 커서 말풍선(Facebook)이 날짜를 가림
STEPS = ["검색", "라이브러리", "게재 날짜", "빌려오기"]
CUR = 2


def grab(t, crop=None):
    if crop:                                   # yuv420 은 짝수 크기만 — 홀수면 데이터가 모자란다
        crop = [crop[0] // 2 * 2, crop[1] // 2 * 2, crop[2] // 2 * 2, crop[3] // 2 * 2]
    vf = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}" if crop else "null"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", SRC, "-frames:v", "1", "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    w, h = (crop[2], crop[3]) if crop else (1920, 1080)
    return Image.frombytes("RGB", (w, h), raw)


def green_mask(img):
    a = np.asarray(img.convert("RGB"), float)
    g = (a[..., 1] - np.maximum(a[..., 0], a[..., 2]))
    m = np.clip((g - 60) * 4, 0, 255).astype(np.uint8)
    return Image.fromarray(m).filter(ImageFilter.MaxFilter(3))


def into_screen(stage, content):
    """무대 이미지의 초록 화면 자리에 content 를 채운다(초록 모양 그대로 — 둥근 모서리·손가락 유지)."""
    m = green_mask(stage)
    bb = m.getbbox()
    x0, y0, x1, y1 = bb
    c = content.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    out = stage.copy()
    out.paste(c, (x0, y0), m.crop(bb))
    return out, bb


def tabs(canvas, y=TOP + 24):
    d = ImageDraw.Draw(canvas)
    f = font(FONT_B, 40)
    n = len(STEPS)
    gap = 16
    w = (W - 60 - gap * (n - 1)) // n
    for i, s in enumerate(STEPS):
        x = 30 + i * (w + gap)
        on = i == CUR
        done = i < CUR
        d.rounded_rectangle([x, y, x + w, y + 84], 20, fill=(255, 212, 0) if on else ((52, 58, 72) if done else (34, 38, 48)))
        d.text((x + w // 2, y + 42), f"{i + 1}  {s}", font=f, fill=(20, 20, 24) if on else (210, 214, 222), anchor="mm")


def finish(canvas, name):
    canvas.paste(title_bar(["대박나는", "광고영상 만드는 법"]), (0, 0))
    cap = caption_img("5월 29일에 게재 시작함", "5월 29일")
    canvas.paste(cap, ((W - cap.width) // 2, CAP_Y - cap.height // 2), cap)
    OUT.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT / f"{name}.png")


def stage_fill(img, top, bottom):
    """무대 이미지를 내용 칸(top~bottom)에 꽉 차게(가로 맞춤, 가운데)."""
    k = W / img.width
    im = img.resize((W, int(img.height * k)), Image.LANCZOS)
    hh = bottom - top
    y = max(0, (im.height - hh) // 2)
    return im.crop((0, y, W, y + hh))


def draft_a():
    # 모니터 무대: 원본 화면(1949.5)을 모니터에 넣고, 화면 안에서 날짜 쪽으로 확대(02편식 키프레임 — 시안은 확대 끝 상태)
    st = Image.open(STAGE / "stage_monitor.png").convert("RGB")
    full = grab(T)
    z = full.crop((470, 480, 470 + 448, 480 + 252))           # 16:9 확대 창(카드 머리만 — 광고주 이름 줄 y≈740 아래는 안 들어오게)
    d = ImageDraw.Draw(z)
    d.rounded_rectangle([50, 86, 50 + 200, 86 + 30], 5, outline=(255, 196, 0), width=3)   # 5.29 줄
    scr, bb = into_screen(st, z)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(stage_fill(scr, TOP, 1380), (0, TOP))
    tabs(canvas)
    finish(canvas, "A_모니터무대_화면안확대")


def window(img, scale, title=""):
    w, h = int(img.width * scale), int(img.height * scale)
    bar = 36
    win = Image.new("RGB", (w, h + bar), (246, 247, 249))
    d = ImageDraw.Draw(win)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([14 + i * 22, 12, 26 + i * 22, 24], fill=c)
    win.paste(img.resize((w, h), Image.LANCZOS), (0, bar))
    m = Image.new("L", win.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, win.width - 1, win.height - 1], 16, fill=255)
    return win, m


def paste_shadow(canvas, im, m, x, y, blur=22, alpha=120):
    sh = Image.new("L", (im.width + 80, im.height + 80), 0)
    sh.paste(m.point(lambda v: int(v * alpha / 255)), (40, 52))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.paste((0, 0, 0), (x - 40, y - 40), sh)
    canvas.paste(im, (x, y), m)


def draft_b():
    # 다크 스튜디오 + 떠 있는 실제 화면 창 두 개(8.21 / 5.29 카드 머리), 겹쳐 쌓임 — 에펙 3D 층 느낌(시안은 정지)
    st = Image.open(STAGE / "stage_studio.png").convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(stage_fill(st, TOP, 1380), (0, TOP))
    c821 = grab(T, [960, 495, 470, 140])
    c529 = grab(T, [505, 495, 470, 140])
    w1, m1 = window(c821, 1.85)
    w2, m2 = window(c529, 1.85)
    paste_shadow(canvas, w1.point(lambda v: int(v * 0.72)), m1, 70, TOP + 170)
    d = ImageDraw.Draw(w2)
    d.rounded_rectangle([34, 36 + 160, 34 + 330, 36 + 160 + 56], 8, outline=(255, 196, 0), width=6)
    paste_shadow(canvas, w2, m2, 150, TOP + 470)
    tabs(canvas)
    finish(canvas, "B_스튜디오_떠있는창")


def draft_c():
    # 폰 무대: 실제 카드 두 장(8.21 · 5.29)을 피드처럼 세로로 쌓아 폰 화면에 — 세로 영상에 세로 화면
    st = Image.open(STAGE / "stage_phone.png").convert("RGB")
    a = grab(T, [960, 495, 440, 230])
    b = grab(T, [505, 495, 440, 230])
    feed = Image.new("RGB", (440, 600), (240, 242, 245))
    feed.paste(a, (0, 10))
    feed.paste(b, (0, 290))
    d = ImageDraw.Draw(feed)
    d.rounded_rectangle([14, 290 + 80, 14 + 190, 290 + 106], 5, outline=(255, 196, 0), width=4)
    scr, bb = into_screen(st, feed)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(stage_fill(scr, TOP, 1380), (0, TOP))
    tabs(canvas)
    finish(canvas, "C_폰무대_피드")


if __name__ == "__main__":
    draft_a()
    draft_b()
    draft_c()
    print(OUT)
