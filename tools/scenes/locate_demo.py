# -*- coding: utf-8 -*-
"""S6 «위치 잡기» 시안 — 보는 사람이 넓은 페이지 어디를 보는지 알게(10-15 사장님 «보는사람이 위치를 알아야지» «1번이맞지»).

순서: 페이지 전체(0.9초) → 말하는 칸에 노란 테두리 → 그 칸으로 한 화면 안 확대(0.4초, 02편식) → 확대 상태 유지 + 구석 미니맵(전체 축소판 + 지금 보는 칸 빨간 사각형).
전체는 실명이 들어오지 않는 높이까지만(광고주 이름 줄 y≈740 위) — 가림 없이.

    python tools/scenes/locate_demo.py   → 납품/빡이사DB_쇼츠/_무대시안/위치잡기_시안.mp4 (무음)
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "scenes"))
from s6_render import title_bar, caption_img, TOP, CAP_Y, W, H, ease_io  # noqa: E402
from stage_drafts import SRC, STAGE, OUT, tabs, stage_fill  # noqa: E402

T = 1946.0                       # 커서 말풍선 없는 프레임
S0 = (0, 150, 1900, 580)         # 페이지 전체(탭·북마크 아래 ~ 광고주 이름 줄 위)
S1 = (505, 495, 440, 240)        # 말하는 칸: 둘째 카드 머리(5.29 게재 시작)
MARK = (522, 574, 236, 30)       # 5.29 줄
FPS, DUR = 30, 5.0
T_MARK, T_Z0, T_Z1, T_MAP = 0.9, 1.5, 1.9, 2.0
WIN_W = 1040
AREA = (TOP + 130, 1360)         # 탭 아래 ~ 자막 위


def grab_full():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{T:.3f}", "-i", SRC, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return Image.frombytes("RGB", (1920, 1080), raw)


def lerp(a, b, q):
    return tuple(x + (y - x) * q for x, y in zip(a, b))


def frame(full, bg, t):
    q = ease_io(min(max((t - T_Z0) / (T_Z1 - T_Z0), 0), 1))
    r = lerp(S0, S1, q)
    canvas = bg.copy()
    # 확대 창: 원본에서 r 을 잘라 폭 WIN_W 로
    h = int(WIN_W * r[3] / r[2])
    view = full.crop((int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3]))).resize((WIN_W, h), Image.LANCZOS)
    if t >= T_MARK:
        k = WIN_W / r[2]
        d = ImageDraw.Draw(view)
        x0, y0 = (MARK[0] - r[0]) * k, (MARK[1] - r[1]) * k
        d.rounded_rectangle([x0, y0, x0 + MARK[2] * k, y0 + MARK[3] * k], 6, outline=(255, 200, 0), width=max(3, int(2 * k ** 0.5)))
    x = (W - WIN_W) // 2
    y = (AREA[0] + AREA[1]) // 2 - h // 2
    m = Image.new("L", view.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, WIN_W - 1, h - 1], 14, fill=255)
    sh = Image.new("L", (WIN_W + 80, h + 80), 0)
    sh.paste(m.point(lambda v: v // 2), (40, 52))
    canvas.paste((0, 0, 0), (x - 40, y - 40), sh.filter(ImageFilter.GaussianBlur(20)))
    canvas.paste(view, (x, y), m)
    if t >= T_MAP:                # 미니맵: 창 오른쪽 위, 전체 축소판 + 지금 보는 칸
        mw = 300
        mh = int(mw * S0[3] / S0[2])
        mp = full.crop((S0[0], S0[1], S0[0] + S0[2], S0[1] + S0[3])).resize((mw, mh), Image.LANCZOS)
        k = mw / S0[2]
        d = ImageDraw.Draw(mp)
        d.rectangle([(S1[0] - S0[0]) * k, (S1[1] - S0[1]) * k, (S1[0] + S1[2] - S0[0]) * k, (S1[1] + S1[3] - S0[1]) * k],
                    outline=(255, 50, 50), width=4)
        fr = Image.new("RGB", (mw + 8, mh + 8), (255, 255, 255))
        fr.paste(mp, (4, 4))
        canvas.paste(fr, (x + WIN_W - fr.width - 10, y - fr.height - 16))
    return canvas


def main():
    full = grab_full()
    bg = Image.new("RGB", (W, H), (0, 0, 0))
    bg.paste(stage_fill(Image.open(STAGE / "stage_studio.png").convert("RGB"), TOP, 1380), (0, TOP))
    tabs(bg)
    bg.paste(title_bar(["대박나는", "광고영상 만드는 법"]), (0, 0))
    cap = caption_img("5월 29일에 게재 시작함", "5월 29일")
    bg.paste(cap, ((W - cap.width) // 2, CAP_Y - cap.height // 2), cap)
    out = OUT / "위치잡기_시안.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)],
                         stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        t = i / FPS
        im = frame(full, bg, t)
        p.stdin.write(im.tobytes())
        if i in (15, 36, 51, 75):
            im.save(ROOT / "_tmp" / "loc" / f"demo_{i:03d}.png")
    p.stdin.close()
    p.wait()
    print(out)


if __name__ == "__main__":
    main()
