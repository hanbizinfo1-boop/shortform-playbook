# -*- coding: utf-8 -*-
"""S6 롱폼 → 세로 쇼츠 조립기 — 편 계획(JSON) 하나로 1080×1920 완성 mp4 + SRT 를 만든다.

    python tools/s6_render.py <계획.json> [--preview 초]   # --preview: 앞 N초만(점검용)

화면 틀(조사 `기록/조사_강의쇼츠구조_1013.md` 2-2): 위 고정 제목 2줄(검정 띠) / 가운데 내용 칸 / 자막 한 줄 /
아래 빈 띠(쇼츠 UI 자리). 끝에 엔딩 카드(얼굴 확대 + 제목 재노출).

계획 JSON 키
  src, out(확장자 없는 경로), fps(30), title:[줄1, 줄2]
  pieces: [{in, out}]                 원본에서 쓸 구간(원본 초). 이어 붙여 출력 시간축이 된다
  shots:  [{from, to, kind, ...}]     원본 초 기준. kind:
      face    : crop=[x,y,w,h] (내용 칸 비율로 잘라 꽉 채움), zoom=[[원본초, 배율], ...] 하드컷 줌
      graphic : crop=[x,y,w,h] → 폭 1080 으로, bg=[r,g,b], header=[x,y,w,h] (위쪽에 따로 얹는 띠), header_scale
      card    : bg_crop=[x,y,w,h](흐린 배경), card_src=원본초, card_crop=[x,y,w,h], card_scale
      freeze  : at=원본초, crop·bg·header 는 graphic 과 같음, push=초당 확대율
  captions: [{from, to, text, hl}]    원본 초. hl = 강조할 부분 문자열(노랑). 폭이 넘치면 자동으로 두 자막으로 나눈다
  sfx: [{at, file, db, align}]        at = 원본 초(그 순간 출력 시각으로 바꿈) 또는 "end"(엔딩 카드 시작)
  ending: {dur, at, crop}             at = 얼굴 정지 프레임 원본 초
수치 근거: 자막 A2 회색 띠(vertical-spec 1장) · 팝 130→100%(0.216초) · 등장 6프레임 감속 · 오버슈트 0.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_B = str(ROOT / "소재" / "fonts" / "Pretendard-Bold.otf")
FONT_XB = str(ROOT / "소재" / "fonts" / "Pretendard-ExtraBold.otf")
W, H = 1080, 1920
# 10-13 사장님 «상단자막바 위치 좀더 밑으로 … 위아래 여백이 비슷하게»: 위 빈칸(0→제목 글자 위) ≈ 아래 빈칸(내용 끝→1920) ≈ 210
TOP, BOT = 440, 1710            # 제목 띠 끝 / 아래 빈 띠 시작 → 내용 칸 440~1710(높이 1270 그대로)
CAP_Y = 1440                    # 자막 띠 중심 y (화면 75%)
TITLE_Y = (255, 357)            # 제목 두 줄 중심 y(84px → 글자 위 끝 ≈ 213)
YELLOW, WHITE, RED = (255, 212, 0), (245, 245, 245), (255, 82, 82)


# ---------- 그림 조각 ----------
def font(path, size):
    return ImageFont.truetype(path, size)


def title_bar(lines):
    im = Image.new("RGB", (W, TOP), (0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(FONT_XB, 84)
    ys = [TITLE_Y[0] - 10, TITLE_Y[1] - 10]
    for ln, y, col in zip(lines, ys, (WHITE, YELLOW)):
        d.text((W // 2, y + 10), ln, font=f, fill=col, anchor="mm")
    return im


def caption_img(text, hl=None):
    """A2 불투명 회색 띠 — 띠 (52,52,56) · 여백 26/14 · 모서리 12 · Pretendard Bold 66 · 흰 245, 강조어만 노랑."""
    f = font(FONT_B, 66)
    w = int(f.getlength(text))
    pad_x, pad_y = 26, 14
    asc, desc = f.getmetrics()
    h = asc + desc
    im = Image.new("RGBA", (w + pad_x * 2, h + pad_y * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], 12, fill=(52, 52, 56, 255))
    x = pad_x
    parts = [(text, WHITE)]
    if hl and hl in text:
        a = text.index(hl)
        parts = [(text[:a], WHITE), (hl, YELLOW), (text[a + len(hl):], WHITE)]
    for s, col in parts:
        if s:
            d.text((x, pad_y), s, font=f, fill=col)
            x += f.getlength(s)
    return im


WORDS = []  # 전사 단어 [{s,e,w}] — 계획의 "words" 경로에서 읽는다


def split_time(c, first_text):
    """뒤 조각 첫 음절이 소리 나는 시각 — 자막 두 조각을 원본 소리에 강제 정렬(align_chars)해서 잰다(못 재면 None → 글자 수 비례).
    (10-14 이전: 전사 단어를 0.3초 앞부터 세어 앞 자막 단어가 섞였다 → «라이브러리라고 뜰 거예요» 0.56초 늦음)"""
    if not SRC_FOR_SPLIT:
        return None
    from align_chars import align
    second = c["text"][len(first_text):].strip()
    rows = align(SRC_FOR_SPLIT[0], max(c["from"] - 0.3, 0), c["to"] + 0.3, [first_text, second])
    if not rows[1] or rows[1][0][0] == "#":
        return None
    return min(max(rows[1][0][1], c["from"] + 0.4), c["to"] - 0.4)


SRC_FOR_SPLIT = []   # render() 가 원본 경로를 넣는다
RENDER_LOG = []      # 렌더 중 스스로 찾은 문제 → _tmp/check/<이름>.render_log.json (점검기가 읽어 ERROR)


_GOOD_END = set("은는이가을를에서로고면며요다죠게도만와과야니까지랑께데나든")   # «의»는 뒤 명사에 붙음(여러분들의 / 눈에 X)
_KEEP_NEXT = ("같은", "같이")      # 앞 명사에 붙는 말 — 이 앞에서 끊는 건 자연스럽다(«인스턴트 양식 / 같은 경우에는»)


def break_cost(left_word, right_word):
    """띄어쓰기 한 곳에서 끊을 때의 어색함(0 = 자연스러움, 1 = 어색함).
    10-14 사장님 «그런데 인스턴트 / 양식 같은경우에는 이아니라 그런데 인스턴트 양식 / 같은 경우에는 이렇게 잘라야지»
    · 앞 말이 조사·어미(은·는·을·를·에서·고·면·요…)나 쉼표로 끝나면 자연스럽다
    · 뒤 말이 «같은·같이»면 자연스럽다
    · 명사 + 명사(«인스턴트 / 양식»), 꾸미는 말 + 꾸밈 받는 말(«넘어갈 / 수»)은 어색하다"""
    lw = left_word.rstrip()
    if not lw:
        return 1.0
    if lw[-1] in ",.?!" or right_word.startswith(_KEEP_NEXT):
        return 0.0
    if right_word in _BOUND or right_word.startswith(("것", "때문", "만큼", "거예", "거거", "겁니")):   # 의존명사(것·거·걸·수·데·줄·때문) 앞에서 끊지 않는다(«밀어주는 / 것을»)
        return 1.0
    if lw in _NOUN_EXC:                        # «고»로 끝나는 명사(광고) — 어미로 오인 금지(«메타 광고 / 라이브러리»)
        return 1.0
    if lw.lstrip("«(\"'") in _DET:              # 뒤 명사를 꾸미는 말(이·그·저·이런…) — 조사 «이»로 오인 금지(10-19 «아하 이 광고주는, 하고 끊어야지»)
        return 1.0
    last = lw[-1]
    if "가" <= last <= "힣":
        jong = (ord(last) - 0xAC00) % 28
        if jong == 8 and last not in "을를": # ㄹ 받침 = 꾸미는 말(갈·할·될·볼) → 뒤 말과 붙여야
            return 1.0
        if last in "는은" and len(lw) >= 2:   # 꾸미는 «-는/-은»(되는·하는·주는·있는·좋은) — 주제 «는»(웹사이트는)과 구분
            prev = lw[-2]
            pj = (ord(prev) - 0xAC00) % 28 if "가" <= prev <= "힣" else -1
            if prev in _VERBISH or pj in (20, 18) or prev in "좋많작높낮같않":
                return 1.0
    return 0.0 if last in _GOOD_END else 1.0


_BOUND = {"것", "거", "걸", "수", "데", "줄", "뿐", "적", "게"}
_NOUN_EXC = {"광고", "최고", "사고", "보고", "재고"}
_DET = {"이", "그", "저", "이런", "그런", "저런", "요런", "이번", "한", "두", "세", "네", "몇", "모든", "각"}
_VERBISH = set("되하주가오보치키리시지기우추내드받")


def split_caption(c, maxw=960):
    """폭이 넘치면 둘로 — 자리는 «어색함(break_cost) + 길이 차이»가 가장 작은 띄어쓰기. 시간은 강제 정렬."""
    f = font(FONT_B, 66)
    t = c["text"]
    if f.getlength(t) + 52 <= maxw or " " not in t:
        return [c]
    sp = [i for i, ch in enumerate(t) if ch == " "]

    def cost(i):
        lw = t[:i].split(" ")[-1]
        rw = t[i + 1:].split(" ")[0]
        over = max(f.getlength(t[:i]), f.getlength(t[i + 1:])) + 52 > maxw   # 나눠도 넘치면 뒤로 미룸
        short = 0.8 if min(len(t[:i].replace(" ", "")), len(t[i + 1:].replace(" ", ""))) < 4 else 0   # «아하, / …» 처럼 한쪽이 3글자 이하
        return break_cost(lw, rw) * 1.0 + abs(i - len(t) / 2) / len(t) + (0.5 if over else 0) + short
    k = min(sp, key=cost)
    a, b = t[:k], t[k + 1:]
    mid = split_time(c, a) or c["from"] + (c["to"] - c["from"]) * len(a) / (len(a) + len(b))
    hl = c.get("hl")
    out = []
    for txt, s, e in ((a, c["from"], mid), (b, mid, c["to"])):
        out += split_caption({"from": s, "to": e, "text": txt, "hl": hl if hl and hl in txt else None}, maxw)
    return out


# ---------- 자료 잘림 방지(10-14 «위아래가 너무잘려있고») ----------
# 자료 화면은 자막 상자 위에서만 보인다(10-14 «레이아웃겹»): 내용 칸 y 0~VP. 자막 상자 위 끝(≈953)보다 28px 위
VP = 925
FADE_OK = False                 # 위·아래 녹임 금지(10-14 «안개낀것같은느낌»)
PIP_SRC = (0, 750, 340, 330)     # 원본 왼쪽 아래 얼굴 원(PIP) 자리 — 잘려 걸치면 배경으로 지운다
PIP_CIRCLE = (156, 933, 156)    # 원본 얼굴 원 실측(중심 x·y, 반지름 — 빡이사DB 10-15). pip 자르기 원은 이 안쪽에(«마스크 뒤에 삐져나온부분 없게»)
SRC_SAFE_BOT = 945               # 원본 이 줄 아래는 구운 자막·작업표시줄 — 맞춤으로 넓혀도 여기를 넘지 않는다(10-14 시험 렌더)
FIT_GROW = 120                   # 맞춤으로 넓히는 최대 폭(원본 px) — 브라우저 위 띠까지 끌고 오지 않게


def row_detail(img, x0=0, x1=None):
    """줄마다 글자·선 밀도(가로 밝기 변화 평균). 여백 줄 ≈ 0~1, 글자 줄 3↑."""
    a = np.asarray(img.convert("L"), float)
    a = a[:, x0:x1]
    return np.abs(np.diff(a, axis=1)).mean(1)


def snap_edge(prof, y, outward, lo, hi, run=6, thr=1.2):
    """y 를 가장 가까운 여백 띠(run 줄 연속 thr 미만)로 옮긴다. outward=-1 위로/+1 아래로 먼저 찾고, 없으면 반대로.
    lo~hi 밖으로는 못 간다. 못 찾으면 None."""
    n = len(prof)
    blank = prof < thr

    def ok(yy):
        a, b = (yy - run, yy) if outward < 0 else (yy, yy + run)
        a, b = max(a, 0), min(b, n)
        return b - a >= 1 and blank[a:b].all()
    for sgn in (outward, -outward):                 # 넓히는 쪽 먼저(더 보여 줌), 없으면 좁히는 쪽
        for d in range(0, 400):
            yy = y + sgn * d
            if lo <= yy <= hi and 0 <= yy <= n and ok(yy):
                return yy
    return None


def fit_crop(src, t, crop, gy, scale, ch, src_h=1080, t_end=None):
    """graphic 자르기 위·아래 끝이 글자를 가르지 않게 여백 줄로 옮긴다(가능하면 넓혀서 더 보여 줌).
    내용 위치는 그대로(gy 를 같이 옮김) → 표시·확대 좌표가 어긋나지 않는다."""
    x, y, w, h = crop
    # 샷 동안 화면이 바뀐다(펼쳐지는 목록·스크롤) → 여러 프레임의 줄 밀도 최댓값으로 잰다(10-14 03편 0~3초 검색 목록)
    ts = [t] if t_end is None else list(np.linspace(t, t_end, 6))
    prof = np.max([row_detail(still(src, tt), x, x + w) for tt in ts], axis=0)
    # 위 끝: 위로 넓히되 내용 칸 위(gy≥0)를 넘지 않게
    up_room = min(int(gy / scale), FIT_GROW)
    ny0 = snap_edge(prof, y, -1, max(0, y - up_room), y + h // 3)
    dn_room = min(int((ch - (gy + h * scale)) / scale), FIT_GROW)
    bot_lim = min(SRC_SAFE_BOT, y + h + max(dn_room, 0)) if y + h <= SRC_SAFE_BOT else y + h
    ny1 = snap_edge(prof, y + h, +1, y + h - h // 3, bot_lim)
    ny0 = y if ny0 is None else ny0
    ny1 = y + h if ny1 is None else ny1
    return [x, ny0, w, ny1 - ny0], gy - (y - ny0) * scale


def fit_zoom(canvas, key, W_, H_, top=0):
    """확대 창(내용 영역 top~top+H_ 안) 위·아래 끝이 글자를 가르면 중심을 조금 옮기거나 배율을 낮춰 여백 줄에 맞춘다."""
    t0, zf, kx, ky = key
    if zf == 1.0:
        return key
    prof = row_detail(canvas)
    cx, cy = (kx or W_ / 2), (ky or top + H_ / 2)
    z = zf
    while z > 1.05:
        hh = H_ / z
        for dy in range(0, int(hh * 0.25), 4):
            for c in (cy + dy, cy - dy):
                y0 = min(max(c - hh / 2, top), top + H_ - hh)
                a, b = int(y0), int(y0 + hh)
                top_ok = a <= top + 2 or prof[max(a - 3, 0):a + 3].max() < 1.2
                bot_ok = b >= top + H_ - 2 or prof[b - 3:min(b + 3, len(prof))].max() < 1.2
                if top_ok and bot_ok:
                    return [t0, round(z, 3), kx, c]
        z -= 0.05
    return [t0, 1.0, 0, 0]


_FADE_CACHE = {}


def paste_faded(canvas, g, gy, fade=48, state=None, x=0, force=None):
    """자료를 붙이되 위·아래 끝 줄에 글자·그림이 걸려 있으면 그 끝을 fade px 에 걸쳐 배경으로 녹인다.
    스크롤되는 화면녹화는 어디서 잘라도 무언가 걸린다 → 칼로 자른 선 대신 부드럽게(10-14 «위아래가 너무잘려있고»)."""
    # 10-14 «위아래 안개낀것같은느낌» — 녹임(페이드)은 쓰지 않는다. 끝이 내용을 가르면 점검기 K 가 잡고, 자르는 자리를 바꾼다.
    if not FADE_OK:
        canvas.paste(g, (x, gy))
        return
    d = row_detail(g.crop((0, 0, g.width, 4))).max(), row_detail(g.crop((0, g.height - 4, g.width, g.height))).max()
    top, bot = d[0] > 1.2 and gy > 0, d[1] > 1.2 and gy + g.height < canvas.height
    if force is not None:            # 확대 창 끝처럼 «잘린 끝»을 부르는 쪽이 아는 경우
        top, bot = force[0], force[1]     # 걸린 끝이면 글자 유무와 상관없이(확대가 움직이는 동안 켜졌다 꺼졌다 하지 않게)
    if state is not None:            # 한 번 녹이기 시작한 끝은 샷 끝까지 유지(켜졌다 꺼졌다 깜빡이지 않게)
        top = state["top"] = state.get("top", False) or top
        bot = state["bot"] = state.get("bot", False) or bot
    if not (top or bot):
        canvas.paste(g, (x, gy))
        return
    key = (g.width, g.height, top, bot, fade)
    m = _FADE_CACHE.get(key)
    if m is None:
        a = np.full((g.height,), 255.0)
        r = np.linspace(0, 255, fade)
        if top:
            a[:fade] = np.minimum(a[:fade], r)
        if bot:
            a[-fade:] = np.minimum(a[-fade:], r[::-1])
        m = Image.fromarray(np.repeat(a[:, None], g.width, 1).astype(np.uint8))
        _FADE_CACHE[key] = m
    canvas.paste(g, (x, gy), m)


def extent(img, x0, y0, cw, chh, size):
    """img 의 (x0,y0,cw,chh) 영역을 size 로 — 좌표를 소수점 그대로 써서 움직임이 떨리지 않는다."""
    return img.transform(size, Image.EXTENT, (x0, y0, x0 + cw, y0 + chh), Image.BICUBIC)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def zoom_state(keys, s, W_, H_, dur=0.3):
    """키프레임 확대: [[원본초, 배율, cx, cy], ...] — 키마다 앞 상태에서 dur 초 동안 부드럽게 옮겨 간다(의도한 움직임만)."""
    z, cx, cy = 1.0, W_ / 2, H_ / 2
    for t0, zf, kx, ky in sorted(keys):
        if s < t0:
            break
        tz, tx, ty = zf, (kx or W_ / 2), (ky or H_ / 2)
        if zf == 1.0:
            tx, ty = W_ / 2, H_ / 2
        q = ease_io((s - t0) / dur)
        z, cx, cy = z + (tz - z) * q, cx + (tx - cx) * q, cy + (ty - cy) * q
    return z, cx, cy


def snap_rect(canvas, rect, kind, pad=28):
    """표시 자리를 실제 글자에 맞춘다(10-14 04편: 눈짐작 좌표라 밑줄이 «딱»이 아니라 «누르면»부터, 동그라미가 글자를 지남).
    밑줄 = 줄 바로 위 글줄(가장 가까운 글줄 덩어리)의 왼끝~오른끝 아래 / 상자·동그라미 = 그 안 글자 덩어리를 감쌈."""
    x, y, w, h = rect
    if kind == "underline":
        reg = (x - pad, y + h - 48, x + w + pad, y + h + 22)          # 아래로도 여유 — 글자 아래를 자르면 밑줄이 글자를 지남
    else:
        reg = (x - pad, y - pad // 2, x + w + pad, y + h + pad // 2)
    reg = [max(int(reg[0]), 0), max(int(reg[1]), 0), min(int(reg[2]), canvas.width), min(int(reg[3]), canvas.height)]
    if reg[2] - reg[0] < 8 or reg[3] - reg[1] < 8:
        return rect
    # 범위 왼·오른 끝에 글자가 걸려 있으면(글자가 범위 밖으로 이어짐) 그쪽으로 20px 씩 넓힌다(최대 120)
    for _ in range(6):
        a = np.asarray(canvas.crop(tuple(reg)).convert("L"), float)
        mk = np.abs(a - np.median(a)) > 45
        grow = False
        if mk[:, :3].any() and reg[0] > 0:
            reg[0] = max(reg[0] - 20, 0)
            grow = True
        if mk[:, -3:].any() and reg[2] < canvas.width:
            reg[2] = min(reg[2] + 20, canvas.width)
            grow = True
        if not grow:
            break
    a = np.asarray(canvas.crop(tuple(reg)).convert("L"), float)
    mk = np.abs(a - np.median(a)) > 45
    rows = mk.sum(1) > 1
    if rows.sum() < 4:
        return rect
    # 글줄 덩어리(이어진 행) 중 밑줄이면 맨 아래(줄에 가장 가까운) 것, 상자면 전체
    ys = np.where(rows)[0]
    if kind == "underline":
        blocks = np.split(ys, np.where(np.diff(ys) > 3)[0] + 1)
        ys = blocks[-1]
    sub = mk[ys.min():ys.max() + 1]
    xs = np.where(sub.sum(0) > 0)[0]
    if len(xs) < 4:
        return rect
    X0, X1 = reg[0] + xs.min(), reg[0] + xs.max()
    Y0, Y1 = reg[1] + ys.min(), reg[1] + ys.max()
    if kind == "underline":
        return [X0 - 4, Y1 + 2, X1 - X0 + 8, 6]
    if kind == "circle":                     # 타원이 글자 네 모서리를 지나지 않게 반지름을 넉넉히
        cx_, cy_ = (X0 + X1) / 2, (Y0 + Y1) / 2
        a_, b_ = (X1 - X0) / 2 * 1.25 + 4, (Y1 - Y0) / 2 * 1.9 + 4     # (1/1.25)²+(1/1.9)² ≈ 0.92 ≤ 1 → 네 모서리가 타원 안
        return [int(cx_ - a_ + 14), int(cy_ - b_ + 14), int(2 * a_ - 28), int(2 * b_ - 28)]
    return [X0 - 10, Y0 - 8, X1 - X0 + 20, Y1 - Y0 + 16]


_OCR = {}


def ocr_rect(canvas, rect, text, kind, pad=12):
    """표시할 글자(text)를 그 순간 화면에서 OCR 로 찾아 정확한 테두리를 쓴다(10-14 «상자가 뭔가 정합성이 안맞는데 가운데 정렬이
    안되었잖아» — 픽셀 덩어리로 찾으면 버튼·휴대폰 테두리·옆 글자가 섞였다). 상자는 상하좌우 같은 여백, 밑줄은 글자 폭 그대로.
    한 줄에 다른 글자가 같이 읽히면 글자 수 비례로 그 부분만. 못 찾으면 None."""
    import difflib
    if "r" not in _OCR:
        import easyocr
        _OCR["r"] = easyocr.Reader(["ko", "en"], gpu=True, verbose=False)
    x, y, w, h = rect
    reg = (max(int(x - 120), 0), max(int(y - 60), 0), min(int(x + w + 120), canvas.width), min(int(y + h + 60), canvas.height))
    want = text.replace(" ", "")
    best = None
    for box, txt, conf in _OCR["r"].readtext(np.asarray(canvas.crop(reg))):
        t = txt.replace(" ", "")
        if not t:
            continue
        # 줄 안에서 want 와 가장 닮은 구간
        L = len(want)
        for i in range(0, max(len(t) - L + 1, 1)):
            for ln in (L - 1, L, L + 1):
                seg = t[i:i + ln]
                if not seg:
                    continue
                r = difflib.SequenceMatcher(None, seg, want).ratio()
                if best is None or r > best[0]:
                    best = (r, box, t, i, len(seg))
    if best is None or best[0] < 0.5:
        return None
    _, box, t, i, ln = best
    xs, ys = [p_[0] for p_ in box], [p_[1] for p_ in box]
    bx0, bx1 = min(xs), max(xs)
    n = max(len(t), 1)
    X0 = reg[0] + bx0 + (bx1 - bx0) * i / n
    X1 = reg[0] + bx0 + (bx1 - bx0) * (i + ln) / n
    Y0, Y1 = reg[1] + min(ys), reg[1] + max(ys)
    # 글자 수 비례는 기호(✕·✓·›)·자간 때문에 밀린다 → 그 줄 높이에서 실제 잉크를 보고 양끝을 다듬는다(18px 넘는 빈칸에서 멈춤)
    band = np.asarray(canvas.crop((0, int(Y0), canvas.width, int(Y1) + 1)).convert("L"), float)
    ink = (np.abs(band - np.median(band)) > 45).any(0)
    c0, c1 = int(max(X0, 0)), int(min(X1, canvas.width - 1))
    if ink[c0:c1 + 1].any():
        cols = np.where(ink[c0:c1 + 1])[0] + c0
        a_, b_ = cols.min(), cols.max()
        while True:                                   # 오른쪽으로 이어지는 잉크(빈칸 ≤ 18px)까지
            nxt = np.where(ink[b_ + 1:min(b_ + 20, canvas.width)])[0]
            if len(nxt) == 0 or b_ + 1 + nxt[0] > X1 + 40:
                break
            b_ = b_ + 1 + nxt.max()
        while True:                                   # 왼쪽도
            prv = np.where(ink[max(a_ - 19, 0):a_])[0]
            if len(prv) == 0 or max(a_ - 19, 0) + prv[-1] < X0 - 40:
                break
            a_ = max(a_ - 19, 0) + prv.min()
        X0, X1 = float(a_), float(b_)
    if kind == "underline":
        return [int(X0), int(Y1 - 4), int(X1 - X0), 6]
    if kind == "circle":
        cx_, cy_ = (X0 + X1) / 2, (Y0 + Y1) / 2
        a_, b_ = (X1 - X0) / 2 * 1.25 + 4, (Y1 - Y0) / 2 * 1.9 + 4
        return [int(cx_ - a_ + 14), int(cy_ - b_ + 14), int(2 * a_ - 28), int(2 * b_ - 28)]
    return [int(X0 - pad), int(Y0 - pad * 0.6), int(X1 - X0 + 2 * pad), int(Y1 - Y0 + 1.2 * pad)]


def draw_marks(canvas, marks, s):
    """도구 연출(10-13 «말할 때 여러 도구를 쓰면서 … 시각적으로 표현»): 형광펜 상자·밑줄·동그라미를 0.3초에 걸쳐 그린다.
    marks: [{"at","to","type":box|underline|circle,"rect":[x,y,w,h](내용 칸 좌표, 대략),"text":감쌀 글자(있으면 OCR 로 정확히),"color"}]"""
    import math
    d = None
    for m in marks:
        if not (m["at"] <= s < m.get("to", 1e9)):
            continue
        if not m.get("_checked"):
            # 표시 자리에 내용이 있는지(10-14 «동그라미가 이렇게 먼저나오는건 어디서 배운연출이야» — 값 글자가 나오기 전에 빈 곳에 그림)
            #   밑줄은 그 위 글자 줄, 상자·동그라미는 안쪽을 본다. 비었으면 렌더 기록에 남기고 점검기가 ERROR 로 막는다
            x, y, w, h = m["rect"]
            reg = (x, y - 70, x + w, y) if m.get("type") == "underline" else (x, y, x + w, y + h)
            reg = tuple(int(v) for v in (max(reg[0], 0), max(reg[1], 0), min(reg[2], canvas.width), min(reg[3], canvas.height)))
            if reg[2] > reg[0] and reg[3] > reg[1] and row_detail(canvas.crop(reg)).max() < 1.5:
                RENDER_LOG.append({"kind": "mark_empty", "src_t": round(s, 2), "type": m.get("type", "box"), "rect": m["rect"]})
            elif m.get("text"):
                r = ocr_rect(canvas, m["rect"], m["text"], m.get("type", "box"))
                if r is None:
                    RENDER_LOG.append({"kind": "mark_text_missing", "src_t": round(s, 2), "text": m["text"]})
                else:
                    m["_rect"] = r
            elif m.get("snap", True):
                m["_rect"] = snap_rect(canvas, m["rect"], m.get("type", "box"))
            m["_checked"] = True
        if d is None:
            d = ImageDraw.Draw(canvas)
        x, y, w, h = m.get("_rect", m["rect"])
        col = tuple(m.get("color", (255, 196, 0)))
        q = ease_out((s - m["at"]) / 0.3)
        tp = m.get("type", "box")
        if tp == "underline":
            d.line([(x, y + h), (x + w * q, y + h)], fill=col, width=10)
        elif tp == "circle":
            d.arc([x - 14, y - 14, x + w + 14, y + h + 14], -90, -90 + 360 * q, fill=col, width=9)
        else:                                           # box: 네 변을 한 붓으로
            per = 2 * (w + h)
            L = per * q
            pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            seg = [w, h, w, h]
            for i in range(4):
                if L <= 0:
                    break
                a, b = pts[i], pts[i + 1]
                f = min(L / seg[i], 1.0)
                d.line([a, (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)], fill=col, width=9)
                L -= seg[i]


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


# ---------- 원본 읽기 ----------
def decode(src, t0, dur, vf, w, h, fps, stretch=1.0):
    pre = f"setpts=PTS*{stretch:.6f}," if abs(stretch - 1) > 1e-6 else ""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur / stretch:.3f}", "-i", src,
           "-vf", f"{pre}fps={fps},{vf},scale={w}:{h}:flags=lanczos,format=rgb24", "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield Image.frombuffer("RGB", (w, h), b, "raw", "RGB", 0, 1)


def still(src, t, crop=None):
    vf = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}" if crop else "null"
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", vf,
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(out)).convert("RGB")


# ---------- 시간축 ----------
class Timeline:
    """pieces 를 이어 붙인 출력 시간축. piece 의 gap(초) = 그 앞에 두는 숨(앞 화면 정지 + 무음)."""

    def __init__(self, pieces):
        self.p, self.gaps, acc = [], [], 0.0
        for pc in pieces:
            g = pc.get("gap", 0.0)
            if g > 0 and self.p:
                self.gaps.append((acc, acc + g))
                acc += g
            self.p.append((pc["in"], pc["out"], acc))
            acc += pc["out"] - pc["in"]
        self.dur = acc

    def in_gap(self, t):
        return any(a <= t < b for a, b in self.gaps)

    def to_out(self, s):
        for a, b, o in self.p:
            if a - 1e-6 <= s <= b + 1e-6:
                return o + s - a
        return None

    def to_src(self, t):
        for a, b, o in self.p:
            if o <= t < o + b - a:
                return a + t - o
        a, b, o = self.p[-1]
        return b


# ---------- 내용 칸 렌더 ----------
CH = BOT - TOP


def shot_for(plan, s):
    for sh in plan["shots"]:
        if sh["from"] - 1e-6 <= s < sh["to"]:
            return sh
    return plan["shots"][-1]


class ShotSource:
    """샷 하나를 원본 시간 구간으로 읽어 내용 칸(1080×CH) 그림을 돌려준다(구간마다 디코더 하나)."""

    def __init__(self, plan, sh, s0, s1, fps):
        self.sh, self.src, self.fps = sh, plan["src"], fps
        k = sh["kind"]
        # src_map=[a,b]: 샷 구간(from~to)을 원본 a~b 로 채운다 — 멈춤 없이 앞쪽 빈 원본 구간을 메울 때(10-13 «멈추는 지점이 없으면»)
        self.stretch = 1.0
        if sh.get("src_map"):
            a, b = sh["src_map"]
            self.stretch = (sh["to"] - sh["from"]) / (b - a)
            s0 = a + (s0 - sh["from"]) / self.stretch
            s1 = a + (s1 - sh["from"]) / self.stretch
        if k == "face":
            x, y, w, h = sh["crop"]
            self.gen = decode(self.src, s0, s1 - s0, f"crop={w}:{h}:{x}:{y}", W, CH, fps)
        elif k == "graphic":
            if sh.get("fit", True) and not sh.get("_fitted"):
                sc0 = W / sh["crop"][2]
                gy0 = sh.get("gy", (CH - int(round(sh["crop"][3] * sc0))) // 2 + 40)
                sh["crop"], gy1 = fit_crop(self.src, sh["from"] + 0.05, sh["crop"], gy0, sc0, CH, t_end=sh["to"] - 0.1)
                sh["gy"], sh["_fitted"] = int(round(gy1)), True
            x, y, w, h = sh["crop"]
            self.gh = int(round(h * W / w))
            # 원본 PIP 얼굴 원이 자르기 경계에 걸치면(반쪽 원) 배경으로 지운다
            px, py, pw, ph_ = PIP_SRC
            ix0, iy0 = max(px, x), max(py, y)
            ix1, iy1 = min(px + pw, x + w), min(py + ph_, y + h)
            inside = px >= x and py >= y and px + pw <= x + w and py + ph_ <= y + h
            sc_ = W / w
            self.erase = []
            if ix1 > ix0 and iy1 > iy0 and (not inside or sh.get("erase_pip")):
                self.erase.append(((ix0 - x) * sc_, (iy0 - y) * sc_, (ix1 - x) * sc_, (iy1 - y) * sc_))
            for m in sh.get("mask", []):                         # 업체명·번호 가림(원본 좌표, [x,y,w,h(,from,to)])
                mx, my, mw, mh = m[:4]
                self.erase.append(((mx - x) * sc_, (my - y) * sc_, (mx + mw - x) * sc_, (my + mh - y) * sc_, "blur",
                                   m[4] if len(m) > 4 else -1e9, m[5] if len(m) > 5 else 1e9))
            self.gen = decode(self.src, s0, (s1 - s0) * self.stretch, f"crop={w}:{h}:{x}:{y}", W, self.gh, fps,
                              self.stretch)
            self.hgen = self._header_gen(s0, s1)
            self.ogens = []
            for ov in sh.get("overlays", []):
                ox, oy, ow, oh = ov["crop"]
                sc = ov.get("scale", 1.0)
                self.ogens.append((ov, decode(self.src, s0, (s1 - s0) * self.stretch, f"crop={ow}:{oh}:{ox}:{oy}",
                                              int(ow * sc) // 2 * 2, int(oh * sc) // 2 * 2, fps, self.stretch)))
        elif k == "pan":
            # hold_until: 원본 장면이 아직 안 들어온 앞부분은 첫 장면(그 시각 프레임)을 보여 준다
            self.hold = sh.get("hold_until", 0)
            if s0 < self.hold:
                self.first = still(self.src, self.hold)
                s0 = self.hold
            self.gen = decode(self.src, s0, s1 - s0, "null", 1920, 1080, fps)
            x, y, w, h = sh["keys"][0][1:]
            self.ph = int(round(h * W / w))
        elif k == "board":
            # 원본 요소를 크게 잘라 놓고 큰 글자·표시를 말에 맞춰 쌓는다(10-14 «편집 스킬 다시 학습해» — tools/scenes/board.py)
            sys.path.insert(0, str(Path(__file__).resolve().parent / "scenes"))
            import board as _board
            self.board = _board.Board(sh, lambda t, crop: still(self.src, t, crop),
                                      lambda t0, dur, vf, w, h: decode(self.src, t0, dur, vf, w, h, fps), fps)
            self.board.start_live(s0, s1)
            self.board.start_spots(s0, s1)
        elif k == "locate":
            # 무대 위 창에 실화면 — 전체 → 말하는 칸으로 들어감, 표시는 글자 경계에 자동 정렬(10-15 «보는사람이 위치를 알아야지»
            #   «정렬좀 제발 똑바로해줘» — tools/scenes/locate.py)
            sys.path.insert(0, str(Path(__file__).resolve().parent / "scenes"))
            import locate as _locate
            self.loc = _locate.Locate(sh, lambda t, crop: still(self.src, t, crop),
                                      lambda t0, dur, vf, w, h: decode(self.src, t0, dur, vf, w, h, fps), RENDER_LOG, fps)
            self.loc.start(s0, s1)
        elif k == "pip":
            cx, cy, r = sh["circle"]
            self.D = sh.get("size", 760)
            self.gen = decode(self.src, s0, s1 - s0, f"crop={2 * r}:{2 * r}:{cx - r}:{cy - r}", self.D, self.D, fps)
            m = Image.new("L", (self.D * 4, self.D * 4), 0)
            ImageDraw.Draw(m).ellipse([0, 0, self.D * 4 - 1, self.D * 4 - 1], fill=255)
            self.mask = m.resize((self.D, self.D), Image.LANCZOS)
        elif k == "card":
            x, y, w, h = sh["bg_crop"]
            self.gen = decode(self.src, s0, s1 - s0, f"crop={w}:{h}:{x}:{y},boxblur=18:2,eq=brightness=-0.18",
                              W, CH, fps)
            cx, cy, cw, chh = sh["card_crop"]
            card = still(self.src, sh["card_src"], [cx, cy, cw, chh])
            sc = sh.get("card_scale", 2.0)
            self.card = card.resize((int(cw * sc), int(chh * sc)), Image.LANCZOS)
            mask = Image.new("L", self.card.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, *[v - 1 for v in self.card.size]], int(14 * sc / 2), fill=255)
            self.card_mask = mask
            self.t0 = 0
        elif k == "push":
            # out = 나가는 화면(원본 초 out_at, out_crop 을 내용 칸에 꽉) / in = 들어오는 화면(graphic 과 같은 배치, in_at)
            ox, oy, ow, oh = sh["out_crop"]
            self.out_img = still(self.src, sh["out_at"], sh["out_crop"]).resize((W, CH), Image.LANCZOS)
            gx, gy0, gw, gh = sh["crop"]
            g_h = int(round(gh * W / gw))
            inn = Image.new("RGB", (W, CH), tuple(sh.get("bg", (242, 242, 240))))
            inn.paste(still(self.src, sh["in_at"], sh["crop"]).resize((W, g_h), Image.LANCZOS), (0, sh.get("gy", 270)))
            if sh.get("header"):
                hx, hy, hw, hh = sh["header"]
                hs = sh.get("header_scale", 1.25)
                hd = still(self.src, sh["in_at"], sh["header"]).resize((int(hw * hs), int(hh * hs)), Image.LANCZOS)
                inn.paste(hd, ((W - hd.width) // 2, sh.get("hy", 40)))
            self.in_img = inn
            self.dur = sh["to"] - sh["from"]
        elif k == "freeze":
            x, y, w, h = sh["crop"]
            self.gh = int(round(h * W / w))
            self.img = still(self.src, sh["at"], sh["crop"]).resize((W, self.gh), Image.LANCZOS)
            self.himg = None
            if sh.get("header"):
                hx, hy, hw, hh = sh["header"]
                hs = sh.get("header_scale", 1.25)
                self.himg = still(self.src, sh["at"], sh["header"]).resize((int(hw * hs), int(hh * hs)), Image.LANCZOS)
        self.n = 0

    def _view(self, canvas, s, top_c, bot_c):
        """카메라: 내용 영역 R(y top_c~bot_c) 안의 창을 «자막 위 영역»(y 0~VP)에 보여 준다.
        z=1 이면 창 = R. R 이 VP 보다 크면 R 전체를 줄여 넣고(가운데·양옆 배경), 확대는 R 안에서만 — 내용이 자막 밑으로
        들어가지 않는다(10-14 «레이아웃겹»). 확대 키 좌표(cx, cy)는 이전과 같은 내용 칸 좌표."""
        sh = self.sh
        top_c, bot_c = max(int(top_c), 0), min(int(bot_c), CH)
        if sh.get("view"):
            top_c, bot_c = sh["view"]
        Hr = max(bot_c - top_c, 1)
        if sh.get("fit", True):
            done = sh.setdefault("_zfit", [])
            for i, key in enumerate(sh.get("zoom", [])):
                if i not in done and s >= key[0]:
                    sh["zoom"][i] = fit_zoom(canvas, key, W, Hr, top_c)
                    done.append(i)
        sc = min(1.0, VP / Hr)
        dw, dh = int(round(W * sc)), int(round(Hr * sc))
        dx, dy = (W - dw) // 2, min(top_c, VP - dh)
        zf, zcx, zcy = zoom_state(sh.get("zoom", []), s, W, CH)
        if abs(zf - 1.0) < 1e-3 and sc == 1.0 and dy == top_c:
            if bot_c > VP:                                   # (이론상 없음) 자막 위 영역 밖은 배경
                canvas.paste(tuple(sh.get("bg", (242, 242, 240))), (0, VP, W, CH))
            return canvas
        ww, wh = W / zf, Hr / zf
        x0 = min(max(zcx - ww / 2, 0), W - ww)
        y0 = min(max(zcy - wh / 2, top_c), bot_c - wh)
        out_ = Image.new("RGB", (W, CH), tuple(sh.get("bg", (242, 242, 240))))
        # 확대 창 위·아래 끝이 내용 중간에 걸리면 그 끝을 배경으로 녹인다(10-14 03편 만화 확대 — 칼로 자른 선 대신)
        cut = (y0 > top_c + 1, y0 + wh < bot_c - 1)
        paste_faded(out_, extent(canvas, x0, y0, ww, wh, (dw, dh)), dy, x=dx, force=cut)
        return out_

    def _header_gen(self, s0, s1):
        if not self.sh.get("header"):
            return None
        x, y, w, h = self.sh["header"]
        hs = self.sh.get("header_scale", 1.25)
        return decode(self.src, s0, (s1 - s0) * self.stretch, f"crop={w}:{h}:{x}:{y}", int(w * hs) // 2 * 2,
                      int(h * hs) // 2 * 2, self.fps, self.stretch)

    def next(self, s):
        sh, k = self.sh, self.sh["kind"]
        t_in = self.n / self.fps
        self.n += 1
        if k == "face":
            fr = next(self.gen, None)
            z = 1.0
            for zt, zv in sh.get("zoom", []):
                if s >= zt:
                    z = zv
            if fr is None:
                fr = getattr(self, "last", Image.new("RGB", (W, CH)))
            self.last = fr
            if z != 1.0:
                cw, chh = int(W / z), int(CH / z)
                fr = fr.crop(((W - cw) // 2, int((CH - chh) * 0.35), (W - cw) // 2 + cw,
                              int((CH - chh) * 0.35) + chh)).resize((W, CH), Image.LANCZOS)
            return fr
        if k in ("graphic", "freeze"):
            canvas = Image.new("RGB", (W, CH), tuple(sh.get("bg", (242, 242, 240))))
            if k == "graphic":
                g = next(self.gen, None) or getattr(self, "last", None)
                self.last = g
                hd = next(self.hgen, None) if self.hgen else None
                if hd is None and self.hgen:
                    hd = getattr(self, "hlast", None)
                self.hlast = hd
            else:
                push = 1 + sh.get("push", 0.0) * t_in
                g = self.img.resize((int(W * push), int(self.gh * push)), Image.LANCZOS)
                g = g.crop(((g.width - W) // 2, (g.height - self.gh) // 2, (g.width - W) // 2 + W,
                            (g.height - self.gh) // 2 + self.gh))
                hd = self.himg
            gy = sh.get("gy", (CH - self.gh) // 2 + 40)
            if g is not None:
                if getattr(self, "erase", None):
                    g = g.copy()
                    dr = ImageDraw.Draw(g)
                    for e in self.erase:
                        box = [int(v) for v in e[:4]]
                        if len(e) > 4 and not (e[5] <= s < e[6]):
                            continue
                        box = [max(box[0], 0), max(box[1], 0), min(box[2], g.width), min(box[3], g.height)]
                        if box[2] <= box[0] or box[3] <= box[1]:
                            continue
                        if len(e) > 4:
                            reg = g.crop(box).filter(ImageFilter.GaussianBlur(9))
                            g.paste(reg, box[:2])
                        else:
                            dr.rectangle(box, fill=tuple(sh.get("bg", (242, 242, 240))))
                paste_faded(canvas, g, gy, state=self.__dict__.setdefault("fade_state", {}))
            # (숨쉬기·드리프트는 폐기 — 10-13 «잔흔들림이 너무 심해». drift 키는 무시한다)
            draw_marks(canvas, sh.get("marks", []), s)
            top_c = min([gy] + ([sh.get("hy", 40)] if sh.get("header") else []))
            canvas = self._view(canvas, s, top_c, gy + self.gh)
            for ov, og in getattr(self, "ogens", []):
                oi = next(og, None)
                if oi is not None and ov.get("from") is not None and not (ov["from"] <= s < ov["to"]):
                    continue
                if oi is not None and ov.get("opaque"):
                    # 화면녹화 입력칸 등 — 타자 치는 동안만 크게(10-13 «지루한 느낌 없게»), 구운 타자음과 짝
                    a = ease_out((s - ov["from"]) / (6 / self.fps))
                    sc = 0.94 + 0.06 * a
                    ci = oi.resize((int(oi.width * sc), int(oi.height * sc)), Image.LANCZOS)
                    mk = Image.new("L", ci.size, 0)
                    ImageDraw.Draw(mk).rounded_rectangle([0, 0, ci.width - 1, ci.height - 1], 14, fill=int(255 * a))
                    shadow = Image.new("RGB", (ci.width + 16, ci.height + 16), (0, 0, 0))
                    sm = Image.new("L", shadow.size, 0)
                    ImageDraw.Draw(sm).rounded_rectangle([0, 0, shadow.width - 1, shadow.height - 1], 20, fill=int(60 * a))
                    sm = sm.filter(ImageFilter.GaussianBlur(8))
                    cx = (W - ci.width) // 2 if ov.get("x") is None else ov["x"]
                    canvas.paste(shadow, (cx - 8, ov["y"] - 2), sm)
                    canvas.paste(ci, (cx, ov["y"]), mk)
                    continue
                if oi is not None:
                    # 배경과 다른 픽셀(카드 내용)만 붙인다 — 카드가 없을 때 빈 조각이 그 자리의 다른 그림을 덮지 않게
                    #   (10-13 «여기 오류났음»: 빈 조각이 뒤에 나오는 말풍선 글자를 가렸다)
                    bgc = np.array(sh.get("bg", (242, 242, 240)), float)
                    diff = np.abs(np.asarray(oi, float) - bgc).max(2)
                    mk = Image.fromarray((np.clip((diff - 6) * 40, 0, 255)).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
                    canvas.paste(oi, (ov["x"], ov["y"]), mk)
            if hd is not None:
                canvas.paste(hd, ((W - hd.width) // 2, sh.get("hy", 40)))
            return canvas
        if k == "pan":
            if s < self.hold:
                fr = self.first
            elif sh.get("hold_after") is not None and s >= sh["hold_after"]:
                next(self.gen, None)                       # 원본 다음 장면 전환이 시작된 뒤 = 직전 프레임 유지
                fr = getattr(self, "last", None)
            else:
                fr = next(self.gen, None) or getattr(self, "last", None)
            self.last = fr
            full = fr.copy()
            for (ax, ay, aw, ah), (bx, by) in sh.get("patch", []):   # 원본 PIP 원 등 가릴 곳을 옆 그림으로 덮음
                full.paste(full.crop((ax, ay, ax + aw, ay + ah)), (bx, by))
            for m in sh.get("mask", []):                                 # 업체명·번호 가림(원본 좌표)
                if len(m) > 4 and not (m[4] <= s < m[5]):
                    continue
                bx0, by0 = max(int(m[0]), 0), max(int(m[1]), 0)
                bx1, by1 = min(int(m[0] + m[2]), 1920), min(int(m[1] + m[3]), 1080)
                if bx1 > bx0 and by1 > by0:
                    full.paste(full.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(9)), (bx0, by0))
            keys = sh["keys"]
            cur = keys[0][1:]
            for (t0k, *c0), (t1k, *c1) in zip(keys, keys[1:]):
                if t0k <= s <= t1k:
                    q = (s - t0k) / max(t1k - t0k, 1e-6)
                    q = q * q * (3 - 2 * q)
                    cur = [c0[j] + (c1[j] - c0[j]) * q for j in range(4)]
                    break
                if s > t1k:
                    cur = c1
            x, y, w, h = cur
            if sh.get("fit", True):
                # 팬 도중 매 프레임 다시 맞추면 떨린다 → 위·아래 값(y,h)마다 한 번, 키 전체 가로 범위로 잰다
                fk = getattr(self, "_pfit", None)
                if fk is None or fk[0] != (round(y), round(h)):
                    kx0 = min(k_[1] for k_ in keys)
                    kx1 = max(k_[1] + k_[3] for k_ in keys)
                    prof = row_detail(full, int(max(kx0, 0)), int(min(kx1, 1920)))
                    ny0 = snap_edge(prof, int(y), -1, max(0, int(y) - FIT_GROW), int(y + h / 4))
                    ny1 = snap_edge(prof, int(y + h), +1, int(y + h * 3 / 4),
                                    min(SRC_SAFE_BOT, int(y + h) + FIT_GROW) if y + h <= SRC_SAFE_BOT else int(y + h))
                    ny0 = y if ny0 is None else ny0
                    ny1 = y + h if ny1 is None else ny1
                    self._pfit = ((round(y), round(h)), ny0, ny1)
                _, ny0, ny1 = self._pfit
                nh = ny1 - ny0
                nw = min(w * nh / h, 1920.0)
                nx = min(max(x + (w - nw) / 2, 0.0), 1920.0 - nw)   # 넓힌 창이 원본 밖(검은 띠)으로 나가지 않게(10-14 03편 오른쪽 띠)
                x, y, w, h = nx, ny0, nw, nh
            img = extent(full, x, y, w, h, (W, self.ph))
            if sh.get("bg_blur", True):
                cov = img.resize((int(W * CH / self.ph), CH), Image.LANCZOS)
                cov = cov.crop(((cov.width - W) // 2, 0, (cov.width - W) // 2 + W, CH)).filter(ImageFilter.GaussianBlur(28))
                canvas = Image.blend(cov, Image.new("RGB", (W, CH), (0, 0, 0)), 0.15)
            else:
                canvas = Image.new("RGB", (W, CH), tuple(sh.get("bg", (242, 242, 240))))
            paste_faded(canvas, img, sh.get("gy", (CH - self.ph) // 2), state=self.__dict__.setdefault("fade_state", {}))
            draw_marks(canvas, sh.get("marks", []), s)
            gy0 = sh.get("gy", (CH - self.ph) // 2)
            return self._view(canvas, s, gy0, gy0 + self.ph)
        if k == "push":
            p = t_in / self.dur
            e = p * p * (3 - 2 * p) if p < 1 else 1.0            # 부드럽게 들어가 부드럽게 멈춤
            off = int(W * e)
            canvas = Image.new("RGB", (W, CH))
            canvas.paste(self.out_img, (-off, 0))
            canvas.paste(self.in_img, (W - off, 0))
            return canvas
        if k == "board":
            return self.board.frame(s)
        if k == "locate":
            return self.loc.frame(s)
        if k == "pip":
            canvas = Image.new("RGB", (W, CH), tuple(sh.get("bg", (242, 242, 240))))
            if sh.get("stage"):                    # 무대 장면 사이 얼굴 — 바탕도 같은 무대(밝은 판으로 튀지 않게)
                st = Image.open(ROOT / "소재" / "ai" / "stage" / sh["stage"]).convert("RGB")
                st = st.resize((W, int(st.height * W / st.width)), Image.LANCZOS)
                y_ = max(0, (st.height - CH) // 2)
                canvas = st.crop((0, y_, W, y_ + CH))
            fr = next(self.gen, None) or getattr(self, "last", None)
            self.last = fr
            a = ease_out(t_in / (9 / self.fps)) if sh.get("grow", True) else 1.0
            d0, d1 = 300, self.D
            d = int(d0 + (d1 - d0) * a)
            x0, y0 = 40, CH - d0 - 140                       # 출발: 원본 PIP 자리(왼쪽 아래)
            x1, y1 = (W - d1) // 2, sh.get("cy", 120)        # 도착: 가운데
            x, y = int(x0 + (x1 - x0) * a), int(y0 + (y1 - y0) * a)
            ring = Image.new("RGB", (d + 12, d + 12), (255, 255, 255))
            rm = self.mask.resize((d + 12, d + 12), Image.LANCZOS)
            canvas.paste(ring, (x - 6, y - 6), rm)
            canvas.paste(fr.resize((d, d), Image.LANCZOS), (x, y), self.mask.resize((d, d), Image.LANCZOS))
            return canvas
        if k == "card":
            fr = next(self.gen, None) or getattr(self, "last", Image.new("RGB", (W, CH)))
            self.last = fr
            fr = fr.copy()                                 # (푸시 인 폐기 — 잔흔들림)
            a = ease_out(t_in / (6 / self.fps))           # 6프레임 감속, 오버슈트 0
            sc = 0.92 + 0.08 * a
            cw, chh = int(self.card.width * sc), int(self.card.height * sc)
            c = self.card.resize((cw, chh), Image.LANCZOS)
            m = self.card_mask.resize((cw, chh)).point(lambda v: int(v * a))
            if sh.get("hl_box") and s >= sh["hl_at"]:
                from PIL import ImageChops
                sc0 = sh.get("card_scale", 2.0) * sc
                hx, hy, hw, hh = [int(v * sc0) for v in sh["hl_box"]]
                prog = ease_out((s - sh["hl_at"]) / 0.25)
                ww = max(1, int(hw * prog))
                region = c.crop((hx, hy, hx + ww, hy + hh))
                c = c.copy()
                c.paste(ImageChops.multiply(region, Image.new("RGB", region.size, (255, 226, 70))), (hx, hy))
            fr.paste(c, ((W - cw) // 2, sh.get("card_y", 300) + (self.card.height - chh) // 2), m)
            return fr
        raise ValueError(k)


# ---------- 본체 ----------
def render(plan, preview=None):
    fps = plan.get("fps", 30)
    src = plan["src"]
    tl = Timeline(plan["pieces"])
    SRC_FOR_SPLIT[:] = [src]
    RENDER_LOG.clear()
    if plan.get("words"):
        WORDS[:] = [w for r in json.loads(Path(plan["words"]).read_text(encoding="utf-8")) for w in r["words"]]
    end = plan.get("ending")          # 10-13 사장님 «마지막에 얼굴나오는건 하지마» → 기본은 넣지 않는다
    tail = plan.get("tail", 0.25)     # 마지막 말 뒤 정지 화면 + 잔향
    total = tl.dur + tail + (end["dur"] if end else 0)
    if preview:
        total = min(total, preview)
    nfr = int(round(total * fps))
    out = Path(plan["out"])
    out.parent.mkdir(parents=True, exist_ok=True)

    bar = title_bar(plan["title"])
    caps = []
    for c in plan["captions"]:
        caps += split_caption(c)
    capx = []
    for c in caps:
        a, b = tl.to_out(c["from"]), tl.to_out(c["to"])
        if a is None or b is None:
            continue
        # 조각 끝 자막은 뒤 숨(gap) 동안 화면에 남아 있으므로 SRT 도 숨 끝까지(10-15 점검 D2 «마지막 음절 전에 사라짐»)
        b += next((g1 - g0 for g0, g1 in tl.gaps if abs(g0 - b) < 0.02), 0.0)
        capx.append((max(0.0, a - 0.05), b, caption_img(c["text"], c.get("hl")), c["text"]))  # 소리보다 0.05초 먼저
    # 앞 자막 끝이 다음 자막 시작(0.05초 당김)을 넘지 않게 — SRT 겹침 없음(10-16 «SRT정합성이 너무 안맞는데»)
    capx = [(a, min(b, capx[i + 1][0]) if i + 1 < len(capx) else b, im, t) for i, (a, b, im, t) in enumerate(capx)]

    # 엔딩 카드 그림
    end_img = None
    if end:
        x, y, w, h = end["crop"]
        face = still(src, end["at"], end["crop"]).resize((W, int(h * W / w)), Image.LANCZOS)
        if face.height < H:
            face = face.resize((int(face.width * H / face.height), H), Image.LANCZOS)
        face = face.crop(((face.width - W) // 2, 0, (face.width - W) // 2 + W, H))
        # 아래쪽에 원본 구운 자막이 걸릴 수 있어 아래 300px 을 검정 그라데이션으로 덮는다
        grad = Image.linear_gradient("L").resize((W, 300))
        face.paste(Image.new("RGB", (W, 300), (0, 0, 0)), (0, H - 300), grad)
        end_img = face

    # typo 장면(엔딩 CTA 타이포): 장면 시간 = 출력 시각 − 그 샷의 첫 출력 시각(조각이 나뉘어도 이어진다)
    typo_start = {}
    for sh in plan["shots"]:
        if sh["kind"] == "typo":
            outs = [tl.to_out(max(a, sh["from"])) for a, b, o in tl.p if b > sh["from"] and a < sh["to"]]
            outs = [x for x in outs if x is not None]
            if outs:
                st0 = min(outs)
                st0 -= next((g1 - g0 for g0, g1 in tl.gaps if abs(g1 - st0) < 1e-6), 0)   # 앞 숨부터 장면 시작
                typo_start[id(sh)] = st0
    if typo_start:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "scenes"))
        import cta_typo
    vtmp = out.with_suffix(".video.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                            "-pix_fmt", "yuv420p", str(vtmp)], stdin=subprocess.PIPE)
    cur_key, cur_src = None, None
    last_frame = Image.new("RGB", (W, H), (0, 0, 0))
    for i in range(nfr):
        t = i / fps
        frame = Image.new("RGB", (W, H), (0, 0, 0))
        last_sh = shot_for(plan, tl.p[-1][1] - 0.01)
        typo_sh = None
        if t >= tl.dur and last_sh["kind"] == "typo":
            typo_sh = last_sh
        elif t < tl.dur and not tl.in_gap(t) and shot_for(plan, tl.to_src(t))["kind"] == "typo":
            typo_sh = shot_for(plan, tl.to_src(t))
        elif tl.in_gap(t):
            nxt = next((o for a, b, o in tl.p if o > t), None)
            if nxt is not None and shot_for(plan, tl.to_src(nxt + 0.001))["kind"] == "typo":
                typo_sh = shot_for(plan, tl.to_src(nxt + 0.001))
        if typo_sh is not None:
            ts = t - typo_start.get(id(typo_sh), t)
            frame.paste(cta_typo.SCENES[typo_sh["scene"]](max(ts, 0.0), typo_sh["beats"]), (0, TOP))
            frame.paste(bar, (0, 0))
            last_frame = frame.copy()
        elif tl.in_gap(t) or (tl.dur <= t < tl.dur + tail):
            frame = last_frame.copy()          # 숨·끝: 앞 화면 정지
        elif t < tl.dur:
            s = tl.to_src(t)
            sh = shot_for(plan, s)
            # 같은 조각·같은 샷이면 디코더를 이어 쓴다
            pidx = next(k for k, (a, b, o) in enumerate(tl.p) if o <= t < o + b - a)
            key = (id(sh), pidx)
            if key != cur_key:
                a, b, o = tl.p[pidx]
                s1 = min(b, sh["to"])
                cur_src, cur_key = ShotSource(plan, sh, s, s1 + 0.2, fps), key
            frame.paste(cur_src.next(s), (0, TOP))
            frame.paste(bar, (0, 0))
            for ci_, (a, b, im, _) in enumerate(capx):
                if a <= t < b:
                    # 10-19 «뭔가 자막나오는 효과가 눈아파»: 자막마다 띠가 사라졌다 0.96→1.0 + 12px 떠오르며 다시 나와 1~2초마다 깜빡였다.
                    # 앞 자막에 바로 이어지면(빈틈 0.3초 미만) 효과 없이 글자만 바꾸고, 빈틈 뒤 첫 자막만 3프레임 페이드(크기·위치 그대로)
                    gap_before = a - capx[ci_ - 1][1] if ci_ else 9.0
                    k = ease_out((t - a) / (3 / fps)) if gap_before >= 0.3 else 1.0
                    al = im.split()[3].point(lambda v, k=k: int(v * k))
                    frame.paste(im, ((W - im.width) // 2, CAP_Y - im.height // 2), al)
                    break
            last_frame = frame.copy()
        else:
            te = t - tl.dur - tail
            push = 1 + 0.05 * te / end["dur"]
            f2 = end_img.resize((int(W * push), int(H * push)), Image.LANCZOS)
            f2 = f2.crop(((f2.width - W) // 2, (f2.height - H) // 2, (f2.width - W) // 2 + W, (f2.height - H) // 2 + H))
            f2 = Image.blend(f2, Image.new("RGB", (W, H), (0, 0, 0)), 0.25)
            d = ImageDraw.Draw(f2)
            fnt = font(FONT_XB, 104)
            for ln, y, col in zip(plan["title"], (H // 2 + 250, H // 2 + 390), (WHITE, YELLOW)):
                d.text((W // 2, y), ln, font=fnt, fill=col, anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
            frame = f2
        enc.stdin.write(frame.tobytes())
        if i % 150 == 0:
            print(f"  {t:5.1f}s / {total:.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()

    # ---------- 소리 ----------
    atmp = out.with_suffix(".audio.wav")
    voice_db = speech_db(src, tl.p)
    inputs, filt, labels = ["-i", src], [], []
    gi = 0
    for k, (a, b, o) in enumerate(tl.p):
        g = next((g1 - g0 for g0, g1 in tl.gaps if abs(g1 - o) < 1e-6), 0)
        if g > 0:
            filt.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{g:.3f}[g{gi}]")
            labels.append(f"[g{gi}]")
            gi += 1
        # 잇는 곳은 25ms 로 열고 45ms 로 닫는다(10-13 «말을 하다가 끊기는 부분»)
        if plan["pieces"][k].get("mute"):
            # 목소리 없는 조각(엔딩 CTA 를 타이포·효과음만으로 — 10-15 «마지막 CTA는 오로지 타이포그래피랑 효과음 같은걸로»)
            filt.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{b - a:.3f}[p{k}]")
        else:
            filt.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                        f"aformat=channel_layouts=stereo,afade=t=in:d=0.025,"
                        f"afade=t=out:st={b - a - plan['pieces'][k].get('fade_out', 0.045):.3f}:"
                        f"d={plan['pieces'][k].get('fade_out', 0.045):.3f}[p{k}]")
        labels.append(f"[p{k}]")
    filt.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1,apad=whole_dur={total:.3f}[voice]")
    mix = ["[voice]"]
    for j, fx in enumerate(plan.get("sfx", [])):
        if "at_typo" in fx:      # 엔딩 타이포 장면 시간 기준(초)
            at = (min(typo_start.values()) if typo_start else tl.dur) + fx["at_typo"]
        else:
            at = tl.dur if fx["at"] == "end" else tl.to_out(fx["at"])
        if at is None or at >= total:
            continue
        lead = peak_offset(fx["file"]) if fx.get("align") == "peak" else 0.0
        st = max(0.0, at - lead)
        inputs += ["-i", fx["file"]]
        # 크기: 들리는 크기(가장 큰 0.1초 RMS)를 목소리 대비 rel dB 에 맞춘다(빡이사 통과표: 휙 −3 · 일반 −2)
        gain = voice_db + fx["rel"] - loud_db(fx["file"]) if "rel" in fx else fx.get("db", 0)
        filt.append(f"[{len(inputs) // 2 - 1}:a]aresample=48000,aformat=channel_layouts=stereo,"
                    f"volume={gain:.1f}dB,"
                    f"adelay={int(st * 1000)}|{int(st * 1000)}[s{j}]")
        mix.append(f"[s{j}]")
    filt.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
                f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[aout]",
                    "-ar", "48000", "-t", f"{total:.3f}", str(atmp)], check=True)
    final = out.with_suffix(".mp4")
    er = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(atmp), "-af", "ebur128", "-f", "null", "-"],
                        capture_output=True, text=True, errors="replace").stderr
    import re as _re
    i_meas = float(_re.findall(r"I:\s+(-?[\d.]+) LUFS", er)[-1])
    adj = -14.0 - i_meas
    # 트루피크 ≤ −1.0 이 될 때까지 리미터를 1dB 씩 낮춘다(AAC 인코딩이 봉우리를 0.5~1.5dB 올린다 — 10-14 03편 −0.1)
    lim = 0.79
    for _ in range(4):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vtmp), "-i", str(atmp), "-c:v", "copy",
                        "-af", f"volume={adj:.2f}dB,alimiter=limit={lim:.3f}:level=false", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", str(final)], check=True)
        er2 = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"],
                             capture_output=True, text=True, errors="replace").stderr
        tp = float(_re.findall(r"Peak:\s+(-?[\d.]+) dBFS", er2)[-1])
        if tp <= -1.0:
            break
        lim *= 0.89
    vtmp.unlink()
    atmp.unlink()

    lg = ROOT / "_tmp" / "check" / (out.name + ".render_log.json")       # 납품 폴더에 두지 않는다
    lg.parent.mkdir(parents=True, exist_ok=True)
    lg.write_text(json.dumps(RENDER_LOG, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- SRT ----------
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    srt = [f"{n}\n{ts(a)} --> {ts(b)}\n{txt}\n" for n, (a, b, _, txt) in enumerate(capx, 1)]
    out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"완성 {final} · {total:.1f}초 · 자막 {len(capx)}줄")


def _rms_series(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{ss:.3f}", "-t", f"{t:.3f}"] if ss is not None else []) + \
          ["-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.int16).astype(float) / 32768
    n = 1600  # 0.1초
    return np.array([20 * np.log10(np.sqrt((x[i:i + n] ** 2).mean()) + 1e-9) for i in range(0, max(len(x) - n, 1), n)])


def loud_db(path):
    """효과음의 들리는 크기 = 가장 큰 0.1초 RMS."""
    return float(_rms_series(path).max())


def speech_db(src, pieces):
    """쓰는 구간 목소리 크기 = 0.1초 RMS 중 말하는 칸(−40dB 위)의 중앙값."""
    v = np.concatenate([_rms_series(src, a, b - a) for a, b, o in pieces])
    return float(np.median(v[v > -40]))


def peak_offset(path):
    """파일 시작 → 들리는 정점(20ms RMS 최대)까지 초 — 휙은 정점을 등장 순간에 맞춘다."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(float)
    n = 320
    r = [np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, max(len(x) - n, 1), n)]
    return int(np.argmax(r)) * n / 16000


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    pl = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    render(pl, float(a[a.index("--preview") + 1]) if "--preview" in a else None)
