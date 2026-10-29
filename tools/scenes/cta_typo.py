# -*- coding: utf-8 -*-
"""엔딩 CTA 타이포·모션 장면 — 사람 없이 편 내용에 맞춘 글자·UI 모션(사장님 10-13 «꼭 사람이 나와야하나? … 타이포그래피같은걸로 … 숏폼 내용에 맞게»).

s6_render 의 kind "typo" 가 scene 이름으로 부른다: frame = SCENES[name](t, beats) → 1080×CH(1270) RGB.
규칙(visual-rules.md 2·4장): 배경 두 겹(단색 금지) · 3색(남색 바탕·흰 글·노랑 강조, 파랑은 UI) · 등장 6프레임 감속 ·
오버슈트 0 · 블러는 입구에만 · 멈춘 글자도 숨 쉰다(+3%/초) · 화면 글은 말을 그대로 따라 쓰지 않는다 · 새 요소 0.6초 간격.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
F_XB = str(ROOT / "소재" / "fonts" / "Pretendard-ExtraBold.otf")
F_B = str(ROOT / "소재" / "fonts" / "Pretendard-Bold.otf")
W, CH, FPS = 1080, 1270, 30
NAVY, WHITE, YELLOW, BLUE = (16, 22, 40), (245, 245, 245), (255, 212, 0), (46, 110, 255)
_cache = {}


def font(p, s):
    k = (p, s)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(p, s)
    return _cache[k]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def background(t):
    """두 겹: 남색 그라데이션 + 천천히 떠도는 흐린 빛(파랑·노랑) + 옅은 점 격자."""
    if "bg" not in _cache:
        g = Image.new("RGB", (W, CH), NAVY)
        d = ImageDraw.Draw(g)
        for y in range(CH):
            k = y / CH
            d.line([(0, y), (W, y)], fill=(int(16 + 10 * k), int(22 + 8 * k), int(40 + 20 * k)))
        dots = Image.new("RGBA", (W, CH), (0, 0, 0, 0))
        dd = ImageDraw.Draw(dots)
        for x in range(30, W, 46):
            for y in range(30, CH, 46):
                dd.ellipse([x - 1.6, y - 1.6, x + 1.6, y + 1.6], fill=(255, 255, 255, 22))
        g.paste(dots, (0, 0), dots)
        _cache["bg"] = g
    bg = _cache["bg"].copy()
    glow = Image.new("RGB", (W, CH), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    bx = 250 + 60 * math.sin(t * 0.6)
    yx = 820 + 50 * math.cos(t * 0.5)
    gd.ellipse([bx - 330, 260 - 330, bx + 330, 260 + 330], fill=(30, 60, 150))
    gd.ellipse([yx - 260, 980 - 260, yx + 260, 980 + 260], fill=(90, 72, 10))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    from PIL import ImageChops
    return ImageChops.add(bg, glow)


def paste_in(canvas, img, xy, t, t0, mode="rise"):
    """등장: 6프레임 감속 페이드 + 18px 떠오름(rise) / 블러 인(blur). 오버슈트 0."""
    if t < t0:
        return
    a = ease((t - t0) / (6 / FPS))
    im = img
    if mode == "blur" and a < 1:
        im = img.filter(ImageFilter.GaussianBlur(10 * (1 - a)))
    x, y = xy
    if mode == "rise":
        y += int(18 * (1 - a))
    al = im.split()[3].point(lambda v, a=a: int(v * a))
    canvas.paste(im, (int(x), int(y)), al)


def bubble(text, w=820, fill=(255, 255, 255), fg=(30, 30, 36), size=46, tail="left", icon=None):
    f = font(F_B, size)
    h = size + 56
    im = Image.new("RGBA", (w, h + 22), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h], 30, fill=fill)
    tx = 36 if tail == "left" else w - 36
    d.polygon([(tx - 14, h - 2), (tx + 14, h - 2), (tx - (8 if tail == "left" else -8), h + 20)], fill=fill)
    x = 34
    if icon:
        d.ellipse([x, (h - 44) // 2, x + 44, (h - 44) // 2 + 44], fill=icon)
        d.text((x + 22, h // 2), "?", font=font(F_XB, 30), fill=WHITE, anchor="mm")
        x += 62
    d.text((x, h // 2), text, font=f, fill=fg, anchor="lm")
    return im


def pill(text, fill=YELLOW, fg=(20, 20, 20), size=50, padx=46):
    f = font(F_XB, size)
    w = int(f.getlength(text)) + padx * 2
    h = size + 44
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=fill)
    ImageDraw.Draw(im).text((w // 2, h // 2), text, font=f, fill=fg, anchor="mm")
    return im


def text_img(text, size, fill=WHITE, f=F_XB):
    fo = font(f, size)
    w = int(fo.getlength(text)) + 8
    im = Image.new("RGBA", (w, size + 30), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4, 0), text, font=fo, fill=fill)
    return im


# ---------------- 장면들 ----------------
def comment_qa(t, b):
    """02편: 문의 손님 관리 → «질문은 댓글로, 대표가 직접 답한다». b = 박자(초) {"label","q1","q2","q3","reply","cta"}."""
    c = background(t)
    paste_in(c, pill("이런 거 물어보세요", fill=(255, 255, 255, 46), fg=WHITE, size=44), (60, 90), t, b["label"], "blur")
    qs = [("완료 문구, 예시 있을까요?", b["q1"]), ("1분 상담 버튼, 어디 넣어요?", b["q2"]), ("우리 업종도 될까요?", b["q3"])]
    for i, (q, t0) in enumerate(qs):
        paste_in(c, bubble(q, w=960, size=54, icon=(120, 130, 150)), (60, 220 + i * 170), t, t0, "rise")
    if t >= b["reply"]:
        rc = Image.new("RGBA", (960, 190), (0, 0, 0, 0))
        d = ImageDraw.Draw(rc)
        d.rounded_rectangle([0, 0, 959, 189], 36, fill=BLUE + (255,))
        d.ellipse([40, 55, 120, 135], fill=WHITE)
        d.line([(60, 96), (77, 113), (104, 78)], fill=BLUE, width=10)
        d.text((150, 50), "대표가 직접", font=font(F_B, 42), fill=(215, 228, 255))
        d.text((150, 100), "하나하나 답변", font=font(F_XB, 62), fill=WHITE)
        paste_in(c, rc, (60, 760), t, b["reply"], "rise")
    if t >= b["cta"]:
        p = pill("댓글로 질문 남기기", size=60)
        k = 1 + 0.025 * math.sin((t - b["cta"]) * 4) if t - b["cta"] > 0.3 else 1
        p2 = p.resize((int(p.width * k), int(p.height * k)), Image.LANCZOS)
        paste_in(c, p2, ((W - p2.width) // 2, 1010 - (p2.height - p.height) // 2), t, b["cta"], "rise")
        ar = text_img("↓", 76, YELLOW)
        if t - b["cta"] > 0.3:
            paste_in(c, ar, ((W - ar.width) // 2, 1130 + int(10 * math.sin((t - b["cta"]) * 5))), t, b["cta"] + 0.3, "rise")
    return c                                               # (푸시 인 폐기 — 10-13 잔흔들림)


def _push(c, t, rate=0.0):
    return c                                               # (푸시 인 폐기 — 10-13 잔흔들림)


def next_ep(t, b):
    """03편 등: «다음 편 예고» — 다음 편 제목 카드 + 구독 알림 칩. b = {"label","card","sub","next":[줄1,줄2]}."""
    c = background(t)
    paste_in(c, pill("다음 편 예고", fill=YELLOW, fg=(20, 20, 20), size=46), (60, 120), t, b["label"], "blur")
    if t >= b["card"]:
        cd = Image.new("RGBA", (960, 470), (0, 0, 0, 0))
        d = ImageDraw.Draw(cd)
        d.rounded_rectangle([0, 0, 959, 469], 40, fill=(255, 255, 255, 255))
        d.rounded_rectangle([50, 50, 230, 230], 30, fill=NAVY + (255,))
        d.polygon([(115, 95), (115, 185), (190, 140)], fill=YELLOW)
        d.text((270, 80), "메타 광고 실전", font=font(F_B, 40), fill=(120, 126, 140))
        d.text((270, 140), b["next"][0], font=font(F_XB, 64), fill=(24, 26, 34))
        d.text((50, 280), b["next"][1], font=font(F_XB, 86), fill=BLUE)
        d.rounded_rectangle([50, 400, 910, 412], 6, fill=(230, 233, 240))
        prog = ease((t - b["card"]) / 1.6)
        d.rounded_rectangle([50, 400, 50 + int(860 * prog), 412], 6, fill=YELLOW)
        paste_in(c, cd, (60, 270), t, b["card"], "rise")
    if t >= b["sub"]:
        p = pill("구독하고 알림 받기", fill=(255, 255, 255, 235), fg=(20, 20, 20), size=54)
        bell = Image.new("RGBA", (p.height, p.height), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bell)
        bd.ellipse([0, 0, p.height - 1, p.height - 1], fill=YELLOW)
        hh = p.height                                   # 종: 몸통(위 둥근 사다리꼴) + 추
        bd.pieslice([hh * 0.28, hh * 0.22, hh * 0.72, hh * 0.66], 180, 360, fill=(20, 20, 20))
        bd.polygon([(hh * 0.28, hh * 0.44), (hh * 0.72, hh * 0.44), (hh * 0.78, hh * 0.68), (hh * 0.22, hh * 0.68)], fill=(20, 20, 20))
        bd.ellipse([hh * 0.43, hh * 0.68, hh * 0.57, hh * 0.80], fill=(20, 20, 20))
        row = Image.new("RGBA", (p.width + p.height + 20, p.height), (0, 0, 0, 0))
        row.paste(bell, (0, 0), bell)
        row.paste(p, (p.height + 20, 0), p)
        paste_in(c, row, ((W - row.width) // 2, 860), t, b["sub"], "rise")
    return _push(c, t)


def industry_chips(t, b):
    """01편: «내 업종은 어떻게 세팅하지?» — 대표가 다루는 업종 칩이 쏟아지고, 빈 칩 «+ 내 업종?» → 댓글 유도.
    업종 목록은 롱폼 00:01 대표 말 그대로(정책자금·보험·피부과·부동산 분양·장기렌트·휴대폰·정수기·프랜차이즈)."""
    c = background(t)
    paste_in(c, text_img("내 업종은", 76), (60, 70), t, b["title"], "blur")
    paste_in(c, text_img("어떻게 세팅하지?", 76, YELLOW), (60, 160), t, b["title"] + 0.2, "blur")
    names = ["정책자금", "보험", "피부과", "부동산 분양", "장기렌트", "휴대폰", "정수기", "프랜차이즈"]
    x, y = 60, 320
    for i, n in enumerate(names):
        ch = pill(n, fill=(255, 255, 255, 34), fg=WHITE, size=46, padx=34)
        if x + ch.width > W - 60:
            x, y = 60, y + ch.height + 22
        paste_in(c, ch, (x, y), t, b["chips"] + i * 0.12, "rise")
        x += ch.width + 18
    y += 120
    if t >= b["mine"]:
        f = font(F_XB, 52)
        txt = "+ 내 업종?"
        w = int(f.getlength(txt)) + 80
        ch = Image.new("RGBA", (w, 100), (0, 0, 0, 0))
        d = ImageDraw.Draw(ch)
        for k in range(0, 2 * (w + 100), 26):          # 점선 테두리
            pass
        d.rounded_rectangle([0, 0, w - 1, 99], 50, outline=YELLOW, width=5)
        d.text((w // 2, 50), txt, font=f, fill=YELLOW, anchor="mm")
        k = 1 + 0.03 * math.sin((t - b["mine"]) * 4) if t - b["mine"] > 0.3 else 1
        ch2 = ch.resize((int(w * k), int(100 * k)), Image.LANCZOS)
        paste_in(c, ch2, ((W - ch2.width) // 2, y + 10), t, b["mine"], "rise")
    if t >= b["cta"]:
        p = pill("댓글에 업종 남기기", size=58)
        paste_in(c, p, ((W - p.width) // 2, 1010), t, b["cta"], "rise")
        ar = text_img("↓", 72, YELLOW)
        if t - b["cta"] > 0.3:
            paste_in(c, ar, ((W - ar.width) // 2, 1125 + int(10 * math.sin((t - b["cta"]) * 5))), t, b["cta"] + 0.3, "rise")
    return _push(c, t)


def order_checklist(t, b):
    """04편: «광고 순서» 체크리스트(4편 대표 말 그대로) + 풀영상 유도. b = {"title","s1","s2","s3","cta"}."""
    c = background(t)
    paste_in(c, text_img("광고비 아끼는", 70), (60, 70), t, b["title"], "blur")
    paste_in(c, text_img("광고 순서", 84, YELLOW), (60, 160), t, b["title"] + 0.2, "blur")
    steps = [("1", "인스턴트 양식으로 DB 받기", b["s1"]), ("2", "DB 200건까지 통화하며 실력 쌓기", b["s2"]),
             ("3", "그다음 랜딩 페이지", b["s3"])]
    for i, (n, txt, t0) in enumerate(steps):
        card = Image.new("RGBA", (960, 150), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([0, 0, 959, 149], 30, fill=(255, 255, 255, 255))
        d.ellipse([30, 35, 110, 115], fill=BLUE if i < 2 else YELLOW)
        d.text((70, 75), n, font=font(F_XB, 48), fill=WHITE if i < 2 else (20, 20, 20), anchor="mm")
        d.text((140, 75), txt, font=font(F_XB, 50 if len(txt) < 14 else 44), fill=(24, 26, 34), anchor="lm")
        if t >= t0 + 0.35:
            q = ease((t - t0 - 0.35) / 0.25)                 # 체크 표시가 그려진다
            d.line([(880, 78), (880 + 14 * q, 92 * 1.0 if q < 0.5 else 92)], fill=BLUE, width=9)
            if q >= 0.5:
                d.line([(894, 92), (894 + 28 * (q - 0.5) * 2, 92 - 34 * (q - 0.5) * 2)], fill=BLUE, width=9)
        paste_in(c, card, (60, 330 + i * 185), t, t0, "rise")
    if t >= b["cta"]:
        p = pill("풀영상에서 그대로 따라하기", size=54)
        paste_in(c, p, ((W - p.width) // 2, 1010), t, b["cta"], "rise")
        ar = text_img("↓", 72, YELLOW)
        if t - b["cta"] > 0.3:
            paste_in(c, ar, ((W - ar.width) // 2, 1120 + int(10 * math.sin((t - b["cta"]) * 5))), t, b["cta"] + 0.3, "rise")
    return c


def next_ep_type(t, b):
    """엔딩 CTA — 목소리 없이 타이포그래피 + 효과음만(10-15 «마지막 CTA는 오로지 타이포그래피랑 효과음 같은걸로 연출해»).
    b = {"label","w1","w2","w3","line","sub","next":[큰말1,큰말2,큰말3]} — 각 말이 한 박자씩 큰 글자로 쌓이고, 마지막 말 밑줄이 그어진 뒤 구독 칩.
    바탕은 본편과 같은 무대(stage_studio)."""
    from pathlib import Path as _P
    st = Image.open(_P(__file__).resolve().parents[2] / "소재" / "ai" / "stage" / "stage_studio.png").convert("RGB")
    st = st.resize((W, int(st.height * W / st.width)), Image.LANCZOS)
    y0 = max(0, (st.height - CH) // 2)
    c = st.crop((0, y0, W, y0 + CH))
    paste_in(c, pill("다음 편", fill=YELLOW, fg=(20, 20, 20), size=50), (70, 110), t, b["label"], "rise")
    ys = [250, 430, 610]
    sizes = [150, 150, 170]
    cols = [WHITE, WHITE, YELLOW]
    for i, key in enumerate(("w1", "w2", "w3")):
        if t >= b[key]:
            im = text_img(b["next"][i], sizes[i], fill=cols[i])
            k = ease((t - b[key]) / (5 / 30))
            sc = 0.86 + 0.14 * k                       # 아래에서 크게 올라오며 자리 잡음(튕김 없음)
            im2 = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
            a_ = im2.split()[3].point(lambda v, k=k: int(v * k))
            c.paste(im2, (70, ys[i] + int(30 * (1 - k)) + (im.height - im2.height) // 2), a_)
            if i == 2 and t >= b["line"]:
                d = ImageDraw.Draw(c)
                q = ease((t - b["line"]) / 0.3)
                d.rounded_rectangle([70, ys[2] + im.height + 14, 70 + int(im.width * q), ys[2] + im.height + 30], 8, fill=YELLOW)
    if t >= b["sub"]:
        p = pill("구독하고 알림 받기", fill=(255, 255, 255, 240), fg=(20, 20, 20), size=54)
        paste_in(c, p, ((W - p.width) // 2, 900), t, b["sub"], "rise")
    return c


def sub_type(t, b):
    """엔딩 구독 CTA — 목소리 없이 타이포그래피 + 효과음만(10-15 «다음편 예고 ㄴㄴ 그냥 구독 CTA쪽으로해»).
    b = {"w1","w2","line","w3","chip","press"} — «도움이 됐다면» → «구독»(크게, 노랑, 밑줄) → «좋아요» → 알림 칩. 바탕은 본편 무대."""
    from pathlib import Path as _P
    st = Image.open(_P(__file__).resolve().parents[2] / "소재" / "ai" / "stage" / "stage_studio.png").convert("RGB")
    st = st.resize((W, int(st.height * W / st.width)), Image.LANCZOS)
    y0 = max(0, (st.height - CH) // 2)
    c = st.crop((0, y0, W, y0 + CH))
    rows = [("w1", "도움이 됐다면", 104, WHITE, 170), ("w2", "구독", 230, YELLOW, 320), ("w3", "좋아요", 150, WHITE, 650)]
    for key, txt, size, colr, y in rows:
        if t < b[key]:
            continue
        im = text_img(txt, size, fill=colr)
        k = ease((t - b[key]) / (5 / 30))
        sc = 0.86 + 0.14 * k
        im2 = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
        a_ = im2.split()[3].point(lambda v, k=k: int(v * k))
        c.paste(im2, ((W - im2.width) // 2, y + int(30 * (1 - k)) + (im.height - im2.height) // 2), a_)
        if key == "w2" and t >= b["line"]:
            q = ease((t - b["line"]) / 0.3)
            d = ImageDraw.Draw(c)
            x0 = (W - im.width) // 2
            d.rounded_rectangle([x0, y + im.height + 10, x0 + int(im.width * q), y + im.height + 30], 10, fill=YELLOW)
    if t >= b["chip"]:
        on = t >= b.get("press", 1e9)                 # 마지막 박자: 칩이 노랗게 켜짐(끝 화면이 멈춰 보이지 않게)
        p = pill("알림 설정까지", fill=YELLOW if on else (255, 255, 255, 240), fg=(20, 20, 20), size=56)
        bell = Image.new("RGBA", (p.height, p.height), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bell)
        hh = p.height
        bd.ellipse([0, 0, hh - 1, hh - 1], fill=(255, 255, 255) if on else YELLOW)
        bd.pieslice([hh * 0.28, hh * 0.22, hh * 0.72, hh * 0.66], 180, 360, fill=(20, 20, 20))
        bd.polygon([(hh * 0.28, hh * 0.44), (hh * 0.72, hh * 0.44), (hh * 0.78, hh * 0.68), (hh * 0.22, hh * 0.68)], fill=(20, 20, 20))
        bd.ellipse([hh * 0.43, hh * 0.68, hh * 0.57, hh * 0.80], fill=(20, 20, 20))
        row = Image.new("RGBA", (p.width + hh + 20, hh), (0, 0, 0, 0))
        row.paste(bell, (0, 0), bell)
        row.paste(p, (hh + 20, 0), p)
        paste_in(c, row, ((W - row.width) // 2, 830), t, b["chip"], "rise")
    return c


_STAGE = {}


def _stage(push):
    """본편 무대 바탕(폭 맞춤) — push 배율로 아주 느리게 민다."""
    from pathlib import Path as _P
    if "img" not in _STAGE:
        _STAGE["img"] = Image.open(_P(__file__).resolve().parents[2] / "소재" / "ai" / "stage" / "stage_studio.png").convert("RGB")
    st = _STAGE["img"]
    w = int(W * push)
    im = st.resize((w, int(st.height * w / st.width)), Image.BILINEAR)
    x0, y0 = (im.width - W) // 2, (im.height - CH) // 2
    return im.crop((x0, y0, x0 + W, y0 + CH))


def sub_bbaksa(t, b=None):
    """엔딩 구독 CTA «광고를 잘하고 싶다면? / 빡이사 구독» — 목소리 없이 모션 타이포 + 효과음
    (10-15 «알림설정까지뺴 그냥 광고를 잘하고 싶다면? 빡이사 구독 딱 이정도면 좋을거같아 빡이사 구독은 에펙이나 리모션으로 잘 만져주고»).
    에펙판(tools/ae/cta_bbaksa.jsx)과 같은 시각표:
      0.00~0.55 «광고를 잘하고 싶다면?» 글자마다 아래에서 올라오며(앞 말끝을 덮지 않게 소리 없음)
      0.90 «빡이사» 흐림 → 선명 · 130 → 100%(튕김 없음) · 1.45 빨간 «구독» 버튼 · 1.80~2.15 커서 → 2.20 누름·물결 → 회색 «구독중»
      2.50~2.95 «빡이사» 위로 빛 한 줄"""
    c = _stage(1.0 + 0.03 * min(t / 4.2, 1))
    # 1) 위 줄 — 글자마다
    f1 = font(F_B, 88)
    line = "광고를 잘하고 싶다면?"
    d0 = ImageDraw.Draw(c)
    total = d0.textlength(line, font=f1)
    x = (W - total) / 2
    n = len(line)
    for i, ch in enumerate(line):
        w_ = d0.textlength(ch, font=f1)
        k = ease((t - 0.55 * i / n) / 0.22)
        if k > 0 and ch != " ":
            lay = Image.new("RGBA", (int(w_) + 20, 140), (0, 0, 0, 0))
            ImageDraw.Draw(lay).text((10, 70), ch, font=f1, fill=WHITE + (int(255 * k),), anchor="lm")
            c.paste(lay, (int(x) - 10, 400 - 70 + int(46 * (1 - k))), lay)
        x += w_
    # 2) «빡이사»
    if t >= 0.9:
        k = ease((t - 0.9) / 0.25)
        big = text_img("빡이사", 250, fill=YELLOW, f=F_XB)
        if t >= 2.5:                                        # 빛 한 줄(글자 안에서만)
            q = (t - 2.5) / 0.45
            if q < 1:
                sh = Image.new("L", big.size, 0)
                cx = -120 + (big.width + 240) * ease(q)
                ImageDraw.Draw(sh).polygon([(cx - 40, 0), (cx + 40, 0), (cx - 20, big.height), (cx - 100, big.height)], fill=170)
                sh = sh.filter(ImageFilter.GaussianBlur(14))
                from PIL import ImageChops
                m = ImageChops.multiply(sh, big.split()[3])
                big.paste((255, 255, 240, 255), (0, 0), m)
        sc = 1.3 - 0.3 * k
        im = big.resize((max(1, int(big.width * sc)), max(1, int(big.height * sc))), Image.LANCZOS)
        if k < 1:
            im = im.filter(ImageFilter.GaussianBlur(18 * (1 - k)))
        a_ = im.split()[3].point(lambda v: int(v * min(1.0, (t - 0.9) / 0.08)))
        c.paste(im, ((W - im.width) // 2, 650 - im.height // 2), a_)
    # 3) 버튼
    if t >= 1.45:
        pop = ease((t - 1.45) / 0.2)
        press = 1.0
        if 2.2 <= t < 2.38:
            u = (t - 2.2) / 0.18
            press = 1 - 0.08 * (1 - abs(2 * u - 1))
        on = min(max((t - 2.2) / 0.1, 0), 1)
        bw, bh = 380, 128
        btn = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        bd = ImageDraw.Draw(btn)
        red, gray = (237, 28, 36), (69, 71, 79)
        fillc = tuple(int(r_ + (g_ - r_) * on) for r_, g_ in zip(red, gray))
        bd.rounded_rectangle([0, 0, bw - 1, bh - 1], bh // 2, fill=fillc + (255,))
        if on < 1:
            bd.text((bw / 2, bh / 2), "구독", font=font(F_XB, 64), fill=(255, 255, 255, int(255 * (1 - on))), anchor="mm")
        if on > 0:
            bd.text((bw / 2, bh / 2), "구독중", font=font(F_XB, 60), fill=(217, 219, 224, int(255 * on)), anchor="mm")
        s_ = pop * press
        bi = btn.resize((max(1, int(bw * s_)), max(1, int(bh * s_))), Image.LANCZOS)
        c.paste(bi, ((W - bi.width) // 2, 960 - bi.height // 2), bi)
        if 2.2 <= t < 2.65:                                   # 누름 물결
            u = ease((t - 2.2) / 0.45)
            rw, rh = int(bw * (1 + 0.28 * u)), int(bh * (1 + 0.4 * u))
            rl = Image.new("RGBA", (rw + 8, rh + 8), (0, 0, 0, 0))
            ImageDraw.Draw(rl).rounded_rectangle([4, 4, rw + 3, rh + 3], (rh + 4) // 2, outline=(255, 255, 255, int(230 * (1 - u))), width=6)
            c.paste(rl, ((W - rl.width) // 2, 960 - rl.height // 2), rl)
    # 4) 커서
    if t >= 1.8:
        q = ease((t - 1.8) / 0.35)
        px, py = 900 + (690 - 900) * q, 1200 + (968 - 1200) * q
        k = 1.0
        if 2.18 <= t < 2.34:
            u = (t - 2.18) / 0.16
            k = 1 - 0.14 * (1 - abs(2 * u - 1))
        al = int(255 * min((t - 1.8) / 0.1, 1))
        poly = [(0, 0), (0, 68), (18, 52), (32, 84), (44, 78), (30, 48), (54, 48)]
        lay = Image.new("RGBA", (W, CH), (0, 0, 0, 0))
        pts = [(px + x_ * k, py + y_ * k) for x_, y_ in poly]
        ld = ImageDraw.Draw(lay)
        ld.polygon(pts, fill=(255, 255, 255, al))
        ld.line(pts + [pts[0]], fill=(20, 20, 26, al), width=5, joint="curve")
        c.paste(lay, (0, 0), lay)
    return c


_CLIP = {}


def ae_clip(t, b):
    """에펙에서 만든 엔딩(10-15 «빡이사 구독은 에펙이나 리모션으로 잘 만져주고») — b = {"file": mov 경로}.
    mov 는 내용 칸 크기(1080×1270) 30fps. 장면 시간 t 의 프레임을 쓰고, 끝을 넘으면 마지막 프레임."""
    import subprocess
    f = b["file"]
    if f not in _CLIP:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vf", f"scale={W}:{CH},format=rgb24", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        n = W * CH * 3
        _CLIP[f] = [Image.frombuffer("RGB", (W, CH), raw[i:i + n], "raw", "RGB", 0, 1) for i in range(0, len(raw) - n + 1, n)]
    fr = _CLIP[f]
    return fr[min(int(t * 30 + 1e-6), len(fr) - 1)].copy()


SCENES = {"sub_bbaksa": sub_bbaksa, "ae_clip": ae_clip, "sub_type": sub_type, "next_ep_type": next_ep_type, "comment_qa": comment_qa, "next_ep": next_ep, "industry_chips": industry_chips, "order_checklist": order_checklist}
