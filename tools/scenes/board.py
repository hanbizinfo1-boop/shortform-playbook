# -*- coding: utf-8 -*-
"""S6 «보드» 장면 — 원본에서 요소 하나를 크게 잘라 놓고, 큰 글자·표시를 말에 맞춰 **쌓는다**. 장면 바꿈은 하드컷(샷 경계).

근거(10-14 사장님 «3편은 모자이크 떡칠» «4편은 위아래 안개낀것같은느낌 + 중간에 키프레임만으로 영상대체하려는 이상한 행동»
«잘되는 쇼츠 레퍼런스 다시 확인해서 편집 스킬 다시 학습해»):
  - 레퍼런스 30편: 자료는 큰 카드·그림, 2~4초마다 내용이 바뀌거나 쌓인다(슈카 1,000만원→3,000만원, 박곰희 칩 쌓기),
    등장은 0~3프레임(튕김 없음), 줌·팬·페이드로 정지 화면을 움직이는 척하지 않는다.
  - 1·2편(통과): 원본에서 요소 하나를 ×2 안팎으로 크게, 말 따라 바꿈.
  - 실화면 녹화(브라우저·광고 라이브러리)는 쓰지 않고 다시 그린다(CLAUDE.md 4 — 가림 블러로 때우지 않는다).

s6_render 의 kind "board" 가 부른다: Board(plan_src, shot).frame(s) → 1080×CH RGB. 좌표는 내용 칸 기준(가로 1080, 세로 0~925 = 자막 위).
layer 종류(모두 "at" = 원본 초, 선택 "until"):
  rect   {rect:[x,y,w,h], fill, outline, width, radius}
  text   {text, x, y, size, color, weight(xb|b|m), anchor(lm|mm|rm…)}
  typing {text, x, y, size, color, dur} — 한 글자씩
  img    {src_t, crop:[x,y,w,h](원본), x, y, w(가로 폭, 비율 유지), radius, shadow}
  live   {crop, x, y, w, radius} — 원본 영상 그대로(움직이는 자료)
  hl     {rect, color} — 형광펜 쓸기(왼→오 0.25초)
  box    {rect, color, width} — 테두리 그리기(0.25초)
  mark   {kind: x|check, x, y, size, color}
  strike {rect, color} — 가로줄 긋기
  cursor {x, y} / {path:[[at,x,y],…]}
  chip   {text, x, y, size, fg, bg, anchor}
  spot   {crop(원본 맥락 영역), x, y, w, src_t(있으면 정지 프레임, 없으면 원본 영상), keys:[[at, fx,fy,fw,fh]|[at,null],…],
          panel:{x,y,maxw,maxh}} — «전체 + 확대»(10-15 «화면이 너무 적게보이니까 … 어떤 페이지에서 어디쯤 저런게 있는지»):
          위는 원본 페이지 전체(초점 밖은 살짝 흐리고 어둡게 = 실명도 안 읽힘), 노란 상자가 초점, 아래 판에 초점 부분을 크게.
          초점 이동은 0.18초(빠른 전환 — «전환을 팍팍팍 빠르게»)
          ※ 10-15 사장님 «위아래 블러처리해서 억지로 맞추는 영상이 난 별로» — 흐린 맥락 창으로 칸을 채우는 쓰임은 금지. 쓰지 않는다
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = {"xb": ROOT / "소재" / "fonts" / "Pretendard-ExtraBold.otf",
         "b": ROOT / "소재" / "fonts" / "Pretendard-Bold.otf",
         "m": ROOT / "소재" / "fonts" / "Pretendard-Bold.otf"}
W, CH, VP = 1080, 1270, 925
APPEAR = 4 / 30          # 등장 4프레임 감속(오버슈트 0) — 레퍼런스 0~3프레임 + 우리 기본값 4~8
DRAW = 0.25              # 형광펜·테두리 그리는 시간
_font = {}


def font(w, s):
    k = (w, s)
    if k not in _font:
        _font[k] = ImageFont.truetype(str(FONTS.get(w, FONTS["b"])), s)
    return _font[k]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def col(c, default=(20, 20, 24)):
    if c is None:
        return default
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


class Board:
    def __init__(self, shot, still_fn, decode_fn, fps=30):
        self.sh, self.fps = shot, fps
        self.bg = col(shot.get("bg"), (244, 244, 242))
        self.imgs = {}
        self.lives = {}
        for i, L in enumerate(shot["layers"]):
            if L["type"] == "img":
                im = still_fn(L["src_t"], L["crop"])
                w = int(L["w"])
                h = int(round(im.height * w / im.width))
                im = im.resize((w, h), Image.LANCZOS)
                self.imgs[i] = (im, self._mask(im.size, L.get("radius", 18)))
            if L["type"] == "live":
                x, y, cw, chh = L["crop"]
                w = int(L["w"]) // 2 * 2
                h = int(round(chh * w / cw)) // 2 * 2
                self.lives[i] = {"gen": None, "size": (w, h), "mask": self._mask((w, h), L.get("radius", 18)), "last": None}
        self.decode_fn = decode_fn
        self.first_s = None
        self.spots = {}
        for i, L in enumerate(shot["layers"]):
            if L["type"] == "spot":
                st = still_fn(L["src_t"], L["crop"]) if L.get("src_t") is not None else None
                self.spots[i] = {"gen": None, "last": st, "static": st is not None}
        self.base = self._background()

    def _mask(self, size, r):
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], r, fill=255)
        return m

    def _background(self):
        """두 겹 바탕: 옅은 세로 그라데이션 + 아주 옅은 점 격자(단색판 금지 — visual-rules 2장)."""
        g = Image.new("RGB", (W, CH), self.bg)
        if self.sh.get("flat"):          # 원본 슬라이드를 그대로 잘라 붙이는 장면 — 바탕을 원본 색 그대로(이음 자국 없게)
            return g
        a = np.asarray(g, float)
        k = np.linspace(0, 1, CH)[:, None, None]
        a = a * (1 - 0.04 * k)
        g = Image.fromarray(a.clip(0, 255).astype(np.uint8))
        d = ImageDraw.Draw(g)
        for x in range(27, W, 54):
            for y in range(27, CH, 54):
                d.ellipse([x - 1.4, y - 1.4, x + 1.4, y + 1.4], fill=tuple(max(v - 14, 0) for v in self.bg))
        return g

    def start_live(self, s0, s1):
        for i, v in self.lives.items():
            L = self.sh["layers"][i]
            x, y, cw, chh = L["crop"]
            v["gen"] = self.decode_fn(s0, s1 - s0, f"crop={cw}:{chh}:{x}:{y}", v["size"][0], v["size"][1])

    def start_spots(self, s0, s1):
        for i, v in self.spots.items():
            if v["static"]:
                continue
            x, y, cw, chh = self.sh["layers"][i]["crop"]
            v["gen"] = self.decode_fn(s0, s1 - s0, f"crop={cw}:{chh}:{x}:{y}", cw // 2 * 2, chh // 2 * 2)

    def _focus(self, keys, s):
        """keys 를 따라 초점 사각형(원본 좌표, 맥락 영역 기준 아님) — 0.18초 감속 이동, null 이면 초점 없음."""
        cur, prev, t0 = None, None, None
        for k in keys:
            if s >= k[0]:
                prev, cur, t0 = cur, (k[1:] if len(k) > 2 else None), k[0]
        if cur is None or prev is None:
            return cur
        q = ease((s - t0) / 0.18)
        return [p + (c - p) * q for p, c in zip(prev, cur)]

    def _draw_spot(self, cv, L, v, s, a):
        im = v["last"]
        if im is None:
            return
        cx, cy, cw, chh = L["crop"]
        w = int(L["w"])
        h = int(round(chh * w / cw))
        sc = w / cw
        ctx = im.resize((w, h), Image.LANCZOS)
        f = self._focus(L["keys"], s)
        x0, y0 = L["x"], L["y"]
        self._shadow(cv, x0, y0, w, h, a, 12)
        if f is None:
            cv.paste(ctx, (x0, y0))
            return
        from PIL import ImageChops  # noqa: F401
        dim = Image.blend(ctx.filter(ImageFilter.GaussianBlur(L.get("blur", 3.5))), Image.new("RGB", ctx.size, (20, 22, 28)),
                          L.get("dim", 0.42))
        fx, fy, fw, fh = f
        bx0, by0 = int((fx - cx) * sc), int((fy - cy) * sc)
        bx1, by1 = int((fx + fw - cx) * sc), int((fy + fh - cy) * sc)
        bx0, by0, bx1, by1 = max(bx0, 0), max(by0, 0), min(bx1, w), min(by1, h)
        dim.paste(ctx.crop((bx0, by0, bx1, by1)), (bx0, by0))
        cv.paste(dim, (x0, y0))
        d = ImageDraw.Draw(cv)
        yc = col(L.get("color"), (255, 200, 0))
        d.rounded_rectangle([x0 + bx0 - 4, y0 + by0 - 4, x0 + bx1 + 4, y0 + by1 + 4], 8, outline=yc, width=5)
        pn = L.get("panel")
        if not pn:
            return
        # 확대 판: 원본 해상도에서 초점 부분을 잘라 판 크기에 맞춤
        rx0, ry0 = max(fx - cx, 0), max(fy - cy, 0)
        z = im.crop((int(rx0), int(ry0), int(min(rx0 + fw, cw)), int(min(ry0 + fh, chh))))
        k = min(pn["maxw"] / z.width, pn["maxh"] / z.height)
        z = z.resize((max(1, int(z.width * k)), max(1, int(z.height * k))), Image.LANCZOS)
        px = pn["x"] + (pn["maxw"] - z.width) // 2
        py = pn["y"] + (pn["maxh"] - z.height) // 2 if pn.get("valign", "top") == "middle" else pn["y"]
        self._shadow(cv, px, py, z.width, z.height, 1.0, 14)
        d.line([(x0 + bx0, y0 + by1 + 4), (px, py)], fill=yc, width=3)
        d.line([(x0 + bx1, y0 + by1 + 4), (px + z.width, py)], fill=yc, width=3)
        cv.paste(z, (px, py), self._mask(z.size, 14))
        d.rounded_rectangle([px - 3, py - 3, px + z.width + 3, py + z.height + 3], 16, outline=yc, width=5)
        L["_panel_box"] = [px, py, z.width, z.height]

    def _shadow(self, canvas, x, y, w, h, a, r=18):
        sh = Image.new("L", (w + 40, h + 40), 0)
        ImageDraw.Draw(sh).rounded_rectangle([20, 24, w + 20, h + 24], r, fill=int(46 * a))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        canvas.paste((0, 0, 0), (x - 20, y - 20), sh)

    def frame(self, s):
        if self.first_s is None:
            self.first_s = s          # 이 장면이 화면에 처음 나온 원본 시각
        cv = self.base.copy()
        d = ImageDraw.Draw(cv)
        for i, L in enumerate(self.sh["layers"]):
            t = L.get("at", -1e9)
            if i in self.lives and self.lives[i]["gen"] is not None:      # 원본 영상은 보이든 말든 매 프레임 읽는다(시각 맞춤)
                fr = next(self.lives[i]["gen"], None)
                if fr is not None:
                    self.lives[i]["last"] = fr
            if i in self.spots and self.spots[i]["gen"] is not None:
                fr = next(self.spots[i]["gen"], None)
                if fr is not None:
                    self.spots[i]["last"] = fr
            if s < t or s >= L.get("until", 1e9):
                continue
            # 장면 첫 요소는 하드컷으로 첫 프레임부터 다 보인다(페이드로 시작하면 빈 화면 한 프레임이 튄다 — 10-15 04편 494.5)
            a = 1.0 if t <= self.first_s + 0.05 or s - t >= APPEAR else ease((s - t) / APPEAR)
            rise = int(16 * (1 - a))
            ty = L["type"]
            if ty == "rect":
                x, y, w, h = L["rect"]
                layer = Image.new("RGBA", (W, CH), (0, 0, 0, 0))
                ImageDraw.Draw(layer).rounded_rectangle(
                    [x, y + rise, x + w, y + h + rise], L.get("radius", 18),
                    fill=col(L.get("fill"), (255, 255, 255)) + (int(255 * a),) if L.get("fill", "#ffffff") else None,
                    outline=col(L.get("outline")) + (int(255 * a),) if L.get("outline") else None,
                    width=L.get("width", 0))
                if L.get("shadow", True) and L.get("fill", "#ffffff"):
                    self._shadow(cv, x, y + rise, w, h, a, L.get("radius", 18))
                cv.paste(layer, (0, 0), layer)
                d = ImageDraw.Draw(cv)
            elif ty in ("text", "typing"):
                txt = L["text"]
                if ty == "typing":
                    n = int(len(txt) * min(max((s - t) / L.get("dur", 0.8), 0), 1))
                    txt = txt[:n]
                    a, rise = 1.0, 0
                if not txt:
                    continue
                f = font(L.get("weight", "xb"), L.get("size", 64))
                c = col(L.get("color"))
                layer = Image.new("RGBA", (W, CH), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                ld.text((L["x"], L["y"] + rise), txt, font=f, fill=c + (int(255 * a),), anchor=L.get("anchor", "lm"),
                        spacing=int(L.get("size", 64) * 0.25), align=L.get("align", "left"))
                if ty == "typing" and n < len(L["text"]) and int(s * 2.5) % 2 == 0:
                    bb = ld.textbbox((L["x"], L["y"]), txt, font=f, anchor=L.get("anchor", "lm"))
                    ld.rectangle([bb[2] + 4, bb[1], bb[2] + 8, bb[3]], fill=c + (255,))
                cv.paste(layer, (0, 0), layer)
                d = ImageDraw.Draw(cv)
            elif ty == "chip":
                f = font("b", L.get("size", 40))
                bb = d.textbbox((0, 0), L["text"], font=f, anchor="lt")
                pw, ph = bb[2] + 2 * int(L.get("size", 40) * 0.6), bb[3] + 2 * int(L.get("size", 40) * 0.35)
                x, y = L["x"], L["y"] + rise
                if L.get("anchor", "lt")[0] == "m":
                    x -= pw // 2
                layer = Image.new("RGBA", (W, CH), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                ld.rounded_rectangle([x, y, x + pw, y + ph], ph // 2, fill=col(L.get("bg"), (32, 92, 255)) + (int(255 * a),))
                ld.text((x + pw // 2, y + ph // 2), L["text"], font=f, fill=col(L.get("fg"), (255, 255, 255)) + (int(255 * a),),
                        anchor="mm")
                cv.paste(layer, (0, 0), layer)
                d = ImageDraw.Draw(cv)
            elif ty in ("img", "live"):
                if ty == "img":
                    im, m = self.imgs[i]
                else:
                    im, m = self.lives[i]["last"], self.lives[i]["mask"]
                    if im is None:
                        continue
                x, y = L["x"], L["y"] + rise
                if L.get("shadow", True):
                    self._shadow(cv, x, y, im.width, im.height, a, L.get("radius", 18))
                cv.paste(im, (x, y), m.point(lambda v_, a=a: int(v_ * a)))
                if L.get("border"):
                    ImageDraw.Draw(cv).rounded_rectangle([x, y, x + im.width - 1, y + im.height - 1], L.get("radius", 18),
                                                         outline=col(L["border"]), width=L.get("border_w", 3))
                d = ImageDraw.Draw(cv)
            elif ty == "spot":
                self._draw_spot(cv, L, self.spots[i], s, a)
                d = ImageDraw.Draw(cv)
            elif ty == "hl":
                x, y, w, h = L["rect"]
                p = ease((s - t) / DRAW)
                ww = max(1, int(w * p))
                reg = cv.crop((x, y, x + ww, y + h))
                from PIL import ImageChops
                cv.paste(ImageChops.multiply(reg, Image.new("RGB", reg.size, col(L.get("color"), (255, 222, 60)))), (x, y))
                d = ImageDraw.Draw(cv)
            elif ty == "box":
                x, y, w, h = L["rect"]
                p = ease((s - t) / DRAW)
                c, lw = col(L.get("color"), (255, 196, 0)), L.get("width", 8)
                per = 2 * (w + h)
                left = per * p
                pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
                for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                    seg = abs(x1 - x0) + abs(y1 - y0)
                    if left <= 0:
                        break
                    q = min(1.0, left / seg)
                    d.line([(x0, y0), (x0 + (x1 - x0) * q, y0 + (y1 - y0) * q)], fill=c, width=lw)
                    left -= seg
                if p >= 1:
                    d.rounded_rectangle([x, y, x + w, y + h], 10, outline=c, width=lw)
            elif ty == "strike":
                x, y, w, h = L["rect"]
                p = ease((s - t) / DRAW)
                d.line([(x, y + h // 2), (x + int(w * p), y + h // 2)], fill=col(L.get("color"), (230, 40, 40)), width=L.get("width", 8))
            elif ty == "mark":
                x, y, r = L["x"], L["y"], L.get("size", 40)
                c = col(L.get("color"), (230, 40, 40) if L["kind"] == "x" else (22, 170, 90))
                p = ease((s - t) / 0.18)
                lw = max(6, r // 4)
                if L["kind"] == "x":
                    d.line([(x - r, y - r), (x - r + 2 * r * p, y - r + 2 * r * p)], fill=c, width=lw)
                    if p >= 1:
                        q = ease((s - t - 0.18) / 0.18)
                        d.line([(x + r, y - r), (x + r - 2 * r * q, y - r + 2 * r * q)], fill=c, width=lw)
                else:
                    pts = [(x - r, y), (x - r * 0.3, y + r * 0.7), (x + r, y - r * 0.8)]
                    d.line(pts[:2] if p < 0.4 else pts, fill=c, width=lw, joint="curve")
            elif ty == "cursor":
                if "path" in L:
                    pth = L["path"]
                    x, y = pth[0][1], pth[0][2]
                    for (t0, x0, y0), (t1, x1, y1) in zip(pth, pth[1:]):
                        if t0 <= s <= t1:
                            q = ease((s - t0) / max(t1 - t0, 1e-6))
                            x, y = x0 + (x1 - x0) * q, y0 + (y1 - y0) * q
                        elif s > t1:
                            x, y = x1, y1
                else:
                    x, y = L["x"], L["y"]
                k = L.get("size", 1.6)
                poly = [(0, 0), (0, 34), (9, 26), (16, 42), (22, 39), (15, 24), (27, 24)]
                pts = [(x + px * k, y + py * k) for px, py in poly]
                d.polygon(pts, fill=(20, 20, 24), outline=(255, 255, 255))
                d.line(pts + [pts[0]], fill=(255, 255, 255), width=3)
        return cv
