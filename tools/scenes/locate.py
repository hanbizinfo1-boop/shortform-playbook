# -*- coding: utf-8 -*-
"""S6 «위치 잡기» 장면 — 무대 위 창에 본편 실화면을 띄우고, 전체 → 말하는 칸으로 한 화면 안에서 들어간다.

근거(10-15 사장님):
  «보는사람이 위치를 알아야지» «1번이맞지» — 전체를 먼저 보여 주고, 말하는 칸에 테두리, 그 칸으로 확대(02편식 한 화면 키프레임).
  «테두리 같은걸로 강조표시할때나 특징같은거 적어줄때 정렬좀 제발 똑바로해줘 … 위치정렬좀 제대로 맞춰줘»
    → 표시(box·hl·strike)는 원본 좌표 대략값을 주면 **실제 글자 픽셀 경계에 자동으로 붙인다**(사방 여백 같게, 화면 px 기준).
    → 라벨은 표시에 묶어 **표시의 왼쪽 끝(아래·위) 또는 세로 가운데(오른쪽·왼쪽)** 에 맞춘다. 같은 장면 라벨은 같은 크기·같은 간격.
    → 맞춤이 안 되면(글자 못 찾음·라벨이 창 밖으로 밀림) RENDER_LOG 에 남겨 점검기가 ERROR.
  «위아래 블러처리해서 억지로 맞추는 영상이 난 별로» — 흐린 채움 없음. 바탕은 디자인 무대(`소재/ai/stage/`).
  «1편에서 왼쪽 상단에있던 4가지 단계를 끌고와서 하나의 화면에 넣은시도도 좋았는데» — 위에 단계 탭.

s6_render 의 kind "locate" 가 부른다. 좌표: cam·marks·patch 는 **원본(1920×1080) 좌표**, 나머지는 내용 칸 좌표.
shot 키:
  src_t   있으면 그 시각 정지 프레임, 없으면 원본 영상 그대로(live)
  cam     [[at, x, y, w, h], …] 카메라(원본 사각형). 첫 키가 전체(위치 잡기). 이동 0.35초 감속
  marks   [{id, at, until, type: box|hl|strike, rect:[x,y,w,h](대략), color, snap(기본 true), dim(전체 화면에서 바깥 어둡게)}]
  labels  [{at, until, text, to: <mark id>, side, bg, fg}] — 같은 장면 같은 크기(label_size)
          side: below|above(표시 왼쪽 끝에 맞춤, align:end 면 오른쪽 끝) · right|left(표시 세로 가운데)
                col_right|col_left(창 밖 한 줄 기둥 — 같은 장면 라벨 x 가 모두 같고, 표시까지 가는 선)
                win_below|win_above(창 바로 아래·위, 창 왼쪽 끝에 맞춤 — 페이지 글자를 덮지 않게)
  patch   [{rect:[x,y,w,h], text}] — 실명 자리를 ○○ 로(원본 배경색으로 덮고 같은 높이 글자). 편당 한두 곳만
  tabs    {steps:[…], cur: i, switch: [초, i]}
  hold_until (live) 이 시각 전은 이 시각 프레임으로 멈춤 — 원본 녹는 전환을 안 보이게
  hold_after (live) 이 시각부터는 직전 프레임 유지 — 원본이 다음 장면으로 넘어가는 전환을 안 보이게
  minimap true 면 확대(전체의 35% 미만) 중 창 오른쪽 위에 전체 축소판 + 지금 보는 칸
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT_B = ROOT / "소재" / "fonts" / "Pretendard-Bold.otf"
FONT_XB = ROOT / "소재" / "fonts" / "Pretendard-ExtraBold.otf"
STAGE = ROOT / "소재" / "ai" / "stage"
W, CH, VP = 1080, 1270, 925
MOVE = 0.35
DRAW = 0.25
PAD = 12                 # 표시 테두리 ↔ 글자 여백(화면 px, 사방 같게)
GAP = 16                 # 표시 ↔ 라벨 간격(화면 px)
WIN_MAX_W = 1040
TAB_Y, TAB_H = 24, 84
AREA = (TAB_Y + TAB_H + 40, VP - 24)     # 창이 놓이는 세로 범위(탭 아래 ~ 자막 위)
_font = {}


def font(p, s):
    k = (str(p), s)
    if k not in _font:
        _font[k] = ImageFont.truetype(str(p), s)
    return _font[k]


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def col(c, d):
    if c is None:
        return d
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


def fit_edges(img, r, reach=48, page=False):
    """카메라 사각형 네 변을 글자를 가르지 않는 빈 줄·빈 칸으로 옮긴다(10-14 «위아래가 너무잘려있고» — 끝이 글자를 자르면 대충 만든 티).
    안쪽으로 먼저 찾고(reach px), 없으면 바깥쪽 조금(reach/3). 원본 밖으로는 안 나간다."""
    g = np.asarray(img.convert("L"), float)
    x, y, w, h = [int(round(v)) for v in r]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, g.shape[1]), min(y + h, g.shape[0])

    # 끝 선 앞뒤 4px 까지 비어 있어야 «빈 줄» — 글자 바로 밑에 붙은 끝은 잘린 것처럼 보인다
    #   «빈» = 그 줄을 따라 밝기가 확 바뀌는 곳이 8곳 이하(카드 테두리·바탕 경계 몇 개는 허용, 글자는 수십 곳)
    def ink_row(v):
        return int((np.abs(np.diff(g[v, x0:x1])) > 25).sum())

    def ink_col(v):
        return int((np.abs(np.diff(g[y0:y1, v])) > 25).sum())

    def blank_row(yy):
        return 4 <= yy < g.shape[0] - 4 and all(ink_row(v) <= 8 for v in range(yy - 4, yy + 5))

    def blank_col(xx):
        return 4 <= xx < g.shape[1] - 4 and all(ink_col(v) <= 8 for v in range(xx - 4, xx + 5))

    def move(v, fn, out):
        # 안쪽(좁히기) 먼저 — 넓히면 계획에서 일부러 뺀 실명 줄·얼굴이 들어올 수 있다(10-15 03 v4 «○○캐피탈» 1947.5)
        if fn(v):
            return v
        for d in range(1, reach):
            if fn(v - out * d):
                return v - out * d
        for d in range(1, reach // 3):
            if fn(v + out * d):
                return v + out * d
        return v
    ny0, ny1 = move(y0, blank_row, -1), move(y1 - 1, blank_row, +1) + 1
    y0, y1 = ny0, ny1
    nx0, nx1 = move(x0, blank_col, -1), move(x1 - 1, blank_col, +1) + 1
    return [int(nx0), int(ny0), int(nx1 - nx0), int(ny1 - ny0)]


def snap(img, rect, grow=3):
    """대략 사각형 안의 실제 글자·그림 픽셀 경계(원본 좌표). 못 찾으면 None, 경계가 대략 사각형 끝에 닿으면 cut=True."""
    x, y, w, h = rect
    X0, Y0 = max(int(x - grow), 0), max(int(y - grow), 0)
    X1, Y1 = min(int(x + w + grow), img.width), min(int(y + h + grow), img.height)
    a = np.asarray(img.crop((X0, Y0, X1, Y1)).convert("RGB"), float)
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bgc = np.median(edge, 0)
    m = np.abs(a - bgc).max(2) > 48
    ys, xs = np.where(m)
    if len(xs) < 4:
        return None, False
    bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    cut = bx0 == 0 or by0 == 0 or bx1 == a.shape[1] or by1 == a.shape[0]
    return [int(X0 + bx0), int(Y0 + by0), int(bx1 - bx0), int(by1 - by0)], bool(cut)


def apply_patch(img, patches):
    if not patches:
        return img
    img = img.copy()
    d = ImageDraw.Draw(img)
    for p in patches:
        x, y, w, h = p["rect"]
        ring = np.asarray(img.crop((x - 3, y - 3, x + w + 3, y + h + 3)).convert("RGB"), float)
        bgc = tuple(int(v) for v in np.median(np.concatenate([ring[0], ring[-1], ring[:, 0], ring[:, -1]]), 0))
        if p.get("fill"):
            bgc = col(p["fill"], bgc)
        d.rectangle([x, y, x + w, y + h], fill=bgc)
        f = font(FONT_B, int(p.get("size", h * 0.8)))
        d.text((x, y + h / 2), p["text"], font=f, fill=col(p.get("color"), (28, 30, 33)), anchor="lm")
    return img


class Locate:
    def __init__(self, shot, still_fn, decode_fn, log, fps=30):
        self.sh, self.fps, self.log = shot, fps, log
        self.still = apply_patch(still_fn(shot["src_t"], None), shot.get("patch")) if shot.get("src_t") is not None else None
        self.decode_fn = decode_fn
        self.gen, self.last = None, self.still
        # hold_until: 원본 장면이 아직 들어오는 중(앞 화면과 겹쳐 녹는 전환)인 앞부분은 다 들어온 프레임으로 멈춰 둔다
        #   (10-16 04편 440.3 — 슬라이드가 광고관리자 화면 위로 녹아 들어옴. 녹임은 «안개» 금지)
        self.hold = None
        if shot.get("src_t") is None and shot.get("hold_until") is not None:
            self.hold = apply_patch(still_fn(shot["hold_until"], None), shot.get("patch"))
            self.last = self.hold
        st = Image.open(STAGE / shot.get("stage", "stage_studio.png")).convert("RGB")
        k = W / st.width
        st = st.resize((W, int(st.height * k)), Image.LANCZOS)
        y = max(0, (st.height - CH) // 2)
        self.base = st.crop((0, y, W, y + CH))
        self.base2 = None
        if shot.get("tabs"):
            tb = shot["tabs"]
            if tb.get("switch"):
                self.base2 = self.base.copy()
                self._tabs(self.base2, dict(tb, cur=tb["switch"][1]))
            self._tabs(self.base, tb)
        self.snapped = {}
        self.fitted = {}
        sz = shot.get("label_size", 46)
        lh = int(sz * 1.6) + GAP
        sides = {lb.get("side") for lb in shot.get("labels", [])}
        self.area = (AREA[0] + (lh if "win_above" in sides else 0), AREA[1] - (lh if "win_below" in sides else 0))
        self.first_s = None

    def start(self, s0, s1):
        if self.still is None:
            h = self.sh.get("hold_until")
            a = max(s0, h) if h is not None else s0
            self.gen = self.decode_fn(a, s1 - a, "null", 1920, 1080) if s1 > a else None

    def _tabs(self, cv, tb):
        d = ImageDraw.Draw(cv)
        f = font(FONT_B, 40)
        n = len(tb["steps"])
        gap = 16
        w = (W - 60 - gap * (n - 1)) // n
        for i, s in enumerate(tb["steps"]):
            x = 30 + i * (w + gap)
            on, done = i == tb["cur"], i < tb["cur"]
            d.rounded_rectangle([x, TAB_Y, x + w, TAB_Y + TAB_H], 20,
                                fill=(255, 212, 0) if on else ((52, 58, 72) if done else (34, 38, 48)))
            d.text((x + w // 2, TAB_Y + TAB_H // 2), f"{i + 1}  {s}", font=f, fill=(20, 20, 24) if on else (210, 214, 222),
                   anchor="mm")

    def key(self, i, img):
        """카메라 키 i — 처음 쓸 때 그 순간 화면으로 끝을 빈 줄에 맞춘다(fit:false 면 그대로)."""
        if i not in self.fitted:
            r = self.sh["cam"][i][1:]
            self.fitted[i] = fit_edges(img, r) if self.sh.get("fit", True) else list(r)
            if self.fitted[i] != list(r):
                self.log.append({"kind": "locate_cam_fit", "src_t": self.sh["cam"][i][0], "from": list(r), "to": self.fitted[i]})
        return self.fitted[i]

    def cam(self, s, img):
        keys = self.sh["cam"]
        cur = self.key(0, img)
        for i in range(1, len(keys)):
            t0 = keys[i][0]
            if s < t0:
                break
            q = ease_io((s - t0) / MOVE)
            cur = [a + (b - a) * q for a, b in zip(self.key(i - 1, img), self.key(i, img))]
        return cur

    def window(self, r):
        """카메라 사각형 → 화면 창(x, y, w, h). 폭 1040 고정, 너무 길면 높이에 맞춤. 세로 가운데."""
        w = WIN_MAX_W
        h = w * r[3] / r[2]
        hmax = self.area[1] - self.area[0]
        if h > hmax:
            h = hmax
            w = h * r[2] / r[3]
        x = (W - w) / 2
        y = (self.area[0] + self.area[1]) / 2 - h / 2
        return x, y, w, h

    def mark_rect(self, img, m):
        """표시의 원본 사각형 — 글자 경계에 붙인 것(한 번만 잰다)."""
        key = id(m)
        if key not in self.snapped:
            if m.get("snap", True):
                r, cut = snap(img, m["rect"])
                if r is None:
                    self.log.append({"kind": "locate_snap_empty", "src_t": m["at"], "rect": m["rect"]})
                    r = list(m["rect"])
                elif cut:
                    self.log.append({"kind": "locate_snap_cut", "src_t": m["at"], "rect": m["rect"], "found": r})
            else:
                r = list(m["rect"])
            self.snapped[key] = r
        return self.snapped[key]

    def frame(self, s):
        if self.first_s is None:
            self.first_s = s
        held = self.hold is not None and s < self.sh["hold_until"]
        after = self.sh.get("hold_after") is not None and s >= self.sh["hold_after"]
        if held:
            self.last = self.hold
        elif after:
            # hold_after: 원본이 다음 장면으로 넘어가기 시작한 뒤는 직전 프레임 유지(10-16 04편 508.5 — 오른쪽에서 밀려오는 전환)
            if self.gen is not None:
                next(self.gen, None)
        elif self.gen is not None:
            fr = next(self.gen, None)
            if fr is not None:
                self.last = apply_patch(fr, self.sh.get("patch"))
        img = self.last
        sw = (self.sh.get("tabs") or {}).get("switch")
        cv = (self.base2 if sw and s >= sw[0] else self.base).copy()
        if img is None:
            return cv
        r = self.cam(s, img)
        wx, wy, ww, wh = self.window(r)
        k = ww / r[2]                                        # 원본 → 화면 배율
        view = img.crop((int(round(r[0])), int(round(r[1])), int(round(r[0] + r[2])), int(round(r[1] + r[3]))))
        view = view.resize((int(round(ww)), int(round(wh))), Image.LANCZOS)

        def to_scr(rx, ry):
            return (rx - r[0]) * k, (ry - r[1]) * k

        boxes = {}
        page = self.key(0, img)
        at_page = abs(r[2] - page[2]) < 1 and abs(r[3] - page[3]) < 1
        d = ImageDraw.Draw(view)
        for m in self.sh.get("marks", []):
            if not (m["at"] <= s < m.get("until", 1e9)):
                continue
            mr = self.mark_rect(img, m)
            x0, y0 = to_scr(mr[0], mr[1])
            x1, y1 = to_scr(mr[0] + mr[2], mr[1] + mr[3])
            ty = m.get("type", "box")
            p = ease((s - m["at"]) / DRAW) if s - m["at"] > 0.0 and m["at"] > self.first_s + 0.05 else 1.0
            if ty == "hl":
                bx = [x0 - 6, y0 - 4, x1 + 6, y1 + 4]
                ww_ = max(1, int((bx[2] - bx[0]) * p))
                reg = view.crop((int(bx[0]), int(bx[1]), int(bx[0]) + ww_, int(bx[3])))
                from PIL import ImageChops
                view.paste(ImageChops.multiply(reg, Image.new("RGB", reg.size, col(m.get("color"), (255, 236, 120)))),
                           (int(bx[0]), int(bx[1])))
                d = ImageDraw.Draw(view)
                boxes[m.get("id")] = bx
                continue
            bx = [x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD]
            boxes[m.get("id")] = bx
            c = col(m.get("color"), (255, 200, 0))
            lw = m.get("width", 6 if not at_page else 8)
            if m.get("dim") and at_page and p > 0:
                dm = Image.new("L", view.size, int(110 * p))
                ImageDraw.Draw(dm).rounded_rectangle([bx[0], bx[1], bx[2], bx[3]], 10, fill=0)
                view.paste((0, 0, 0), (0, 0), dm)
                d = ImageDraw.Draw(view)
            if ty == "strike":
                yy = (y0 + y1) / 2
                d.line([(x0 - 4, yy), (x0 - 4 + (x1 - x0 + 8) * p, yy)], fill=col(m.get("color"), (230, 40, 40)), width=lw)
                continue
            if p < 1:
                per = 2 * ((bx[2] - bx[0]) + (bx[3] - bx[1]))
                left = per * p
                pts = [(bx[0], bx[1]), (bx[2], bx[1]), (bx[2], bx[3]), (bx[0], bx[3]), (bx[0], bx[1])]
                for (ax, ay), (bx_, by_) in zip(pts, pts[1:]):
                    seg = abs(bx_ - ax) + abs(by_ - ay)
                    if left <= 0:
                        break
                    q = min(1.0, left / seg)
                    d.line([(ax, ay), (ax + (bx_ - ax) * q, ay + (by_ - ay) * q)], fill=c, width=lw)
                    left -= seg
            else:
                d.rounded_rectangle(bx, 10, outline=c, width=lw)

        # 창(그림자 + 둥근 모서리)
        ix, iy = int(round(wx)), int(round(wy))
        m_ = Image.new("L", view.size, 0)
        ImageDraw.Draw(m_).rounded_rectangle([0, 0, view.width - 1, view.height - 1], 16, fill=255)
        sh = Image.new("L", (view.width + 80, view.height + 80), 0)
        sh.paste(m_.point(lambda v: v // 2), (40, 54))
        cv.paste((0, 0, 0), (ix - 40, iy - 40), sh.filter(ImageFilter.GaussianBlur(20)))
        cv.paste(view, (ix, iy), m_)
        d = ImageDraw.Draw(cv)

        # 라벨: 표시에 맞춰 정렬(화면 좌표 = 창 위치 + 표시 상자)
        size = self.sh.get("label_size", 46)
        f = font(FONT_B, size)
        for lb in self.sh.get("labels", []):
            if not (lb["at"] <= s < lb.get("until", 1e9)):
                continue
            bx = boxes.get(lb["to"])
            if bx is None:
                self.log.append({"kind": "locate_label_orphan", "src_t": lb["at"], "text": lb["text"]})
                continue
            bx = [bx[0] + ix, bx[1] + iy, bx[2] + ix, bx[3] + iy]
            tb = d.textbbox((0, 0), lb["text"], font=f, anchor="lt")
            pw, ph = tb[2] + int(size * 1.1), int(size * 1.6)
            side = lb.get("side", "below")
            lead = None
            if side == "col_right":
                x, y = ix + view.width + GAP + 8, (bx[1] + bx[3]) / 2 - ph / 2
                lead = ((bx[2], (bx[1] + bx[3]) / 2), (x, (bx[1] + bx[3]) / 2))
            elif side == "col_left":
                x, y = ix - GAP - 8 - pw, (bx[1] + bx[3]) / 2 - ph / 2
                lead = ((bx[0], (bx[1] + bx[3]) / 2), (x + pw, (bx[1] + bx[3]) / 2))
            elif side == "win_below":
                x, y = ix, iy + view.height + GAP
                if lb.get("align") == "end":
                    x = ix + view.width - pw
            elif side == "win_above":
                x, y = ix, iy - GAP - ph
                if lb.get("align") == "end":
                    x = ix + view.width - pw
            elif side == "below":
                x, y = bx[0], bx[3] + GAP
            elif side == "above":
                x, y = bx[0], bx[1] - GAP - ph
            elif side == "right":
                x, y = bx[2] + GAP, (bx[1] + bx[3]) / 2 - ph / 2
            else:
                x, y = bx[0] - GAP - pw, (bx[1] + bx[3]) / 2 - ph / 2
            if lb.get("align") == "end" and side in ("below", "above"):
                x = bx[2] - pw
            if side in ("col_right", "col_left", "win_below", "win_above"):
                pass
            x0c = min(max(x, 16), W - 16 - pw)
            y0c = min(max(y, AREA[0] - 40), VP - ph)
            if abs(x0c - x) > 1 or abs(y0c - y) > 1:
                self.log.append({"kind": "locate_label_shifted", "src_t": lb["at"], "text": lb["text"],
                                 "dx": round(x0c - x), "dy": round(y0c - y)})
            x, y = x0c, y0c
            a = 1.0 if lb["at"] <= self.first_s + 0.05 else ease((s - lb["at"]) / (4 / 30))
            layer = Image.new("RGBA", (W, CH), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            if lead:
                (lx0, ly0), (lx1, ly1) = lead
                lc = col(lb.get("line"), (255, 200, 0)) + (int(255 * a),)
                ld.line([(lx0, ly0), (lx1 if lx1 > lx0 else x + pw, ly1)], fill=lc, width=4)
                ld.ellipse([lx0 - 6, ly0 - 6, lx0 + 6, ly0 + 6], fill=lc)
            # 라벨은 자막(어두운 반투명 판 + 흰 글자)과 모양이 달라야 한다(10-15 «자막이랑 저렇게 모양이 같으면 안돼 구분가게끔»)
            #   → 기본: 흰 판 + 진한 글자 + 왼쪽 노란 띠(표시 테두리와 같은 색 = 그 표시의 이름표). bg 를 주면 그 색 판 + 흰 글자
            if lb.get("bg"):
                ld.rounded_rectangle([x, y, x + pw, y + ph], 10, fill=col(lb["bg"], (22, 24, 29)) + (int(255 * a),))
                fg = col(lb.get("fg"), (255, 255, 255))
                tx = x + pw / 2
            else:
                ld.rounded_rectangle([x, y, x + pw, y + ph], 10, fill=(255, 255, 255, int(255 * a)))
                ld.rounded_rectangle([x, y, x + 12, y + ph], 6, fill=(255, 200, 0, int(255 * a)))
                ld.rectangle([x + 6, y, x + 12, y + ph], fill=(255, 200, 0, int(255 * a)))
                fg = col(lb.get("fg"), (22, 24, 29))
                tx = x + 6 + pw / 2
            ld.text((tx, y + ph / 2), lb["text"], font=f, fill=fg + (int(255 * a),), anchor="mm")
            cv.paste(layer, (0, 0), layer)
            d = ImageDraw.Draw(cv)

        # 미니맵: 창 오른쪽 끝에 맞춰 위에
        if self.sh.get("minimap") and r[2] * r[3] < 0.35 * page[2] * page[3]:
            mw = 280
            mh = int(mw * page[3] / page[2])
            mp = img.crop((page[0], page[1], page[0] + page[2], page[1] + page[3])).resize((mw, mh), Image.LANCZOS)
            q = mw / page[2]
            ImageDraw.Draw(mp).rectangle([(r[0] - page[0]) * q, (r[1] - page[1]) * q, (r[0] + r[2] - page[0]) * q,
                                          (r[1] + r[3] - page[1]) * q], outline=(255, 50, 50), width=4)
            fr = Image.new("RGB", (mw + 8, mh + 8), (255, 255, 255))
            fr.paste(mp, (4, 4))
            mx = ix + view.width - fr.width
            my = iy - fr.height - 14
            if my >= AREA[0] - 30:
                cv.paste(fr, (mx, my))
        return cv
