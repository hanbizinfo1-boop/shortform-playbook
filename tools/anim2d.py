# -*- coding: utf-8 -*-
"""S7 2D 재현 설명 쇼츠 조립기 — 계획 JSON 하나로 1080×1920 mp4 + SRT. 유료 영상화 없이 Codex 레이어 + 코드 모션.

    python tools/anim2d.py <계획.json> [--preview 초] [--frames 출력시각,...]   # --frames: 그 시각 정지 PNG 만(점검용)

방향(10-29 사장님): «2d로 재현해서 설명하는 느낌» «계속 움직이면서 지루하지않은 … 귀엽거나 그런거보단 세련되게»
«쇼츠는 어지간하면 힉스필드안썼으면좋겠어 무조건 2d로». 설계 `.claude/skills/shortform/references/s7-2d-explainer.md`.

계획 JSON 키
  src(원본 영상 — 목소리만 씀), out(확장자 없는 경로), fps(30), layers(레이어 폴더 — *_cut.png 를 먼저 찾음)
  pieces: [{in, out}]  원본에서 쓸 말 구간(원본 초). 이어 붙여 출력 시간축
  scenes: [{from, to, bg, bg_depth, cam, items}]   from/to = 원본 초(출력으로 바꿈). 장면 사이는 하드컷
      cam  : [[t, zoom, dx, dy], ...]  장면 안 초. 없으면 1.00→1.06 천천히 밀기(정지 화면 금지)
      items: 아래 종류. 공통 키 t0(나타남, 장면 안 초) · t1(사라짐) · depth(카메라 따라감 0~1.2, 기본 1)
        sprite : file, x, y(중심), h(높이 px), keys [[t, {x,y,s,r,a}]] 감속 보간, bob [진폭px, 주기초], flip
                 poses [[t, file], ...] 그 시각부터 그림 바꿈(연기)
        stream : file, p0[x,y], p1[x,y], h, every(초), travel(초), spin(도/초), jitter(px), arc(px) — 끝없이 흘러가는 물건
        text   : text, x, y, size, color, weight(b|xb), box(색 → 판), count [from, to, 초](숫자 올라감), suffix
        hands  : x, y, r, speed(바퀴/초) — 시계 바늘
        fill   : file(내용물), rect[x,y,w,h], level [[t, 0~1], ...] — 아래부터 차오르는/빠지는 내용물(탱크)
        card   : x, y, w, h, icon(file), color — 둥근 판(알파 255, 반경 14)
        arrow  : p0, p1, color, width, grow(초)
  captions: [{from, to, text, hl}]  원본 초. 폭 넘치면 자동으로 나눔(s6_render.split_caption)
규칙(visual-rules): 등장 감속 6프레임 · 오버슈트 0 · 흔들림 금지 · 새 요소 혼자 0.6초 · 글자는 렌더러가 그림.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s6_render as s6  # noqa: E402  (자막 판·나누기·글꼴을 그대로 쓴다)

ROOT = s6.ROOT
W, H = 1080, 1920
CAP_Y = 1500
_IMG = {}


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def load(layers, name):
    if name not in _IMG:
        p = Path(layers) / name
        cut = p.with_name(p.stem + "_cut.png")
        _IMG[name] = Image.open(cut if cut.exists() else p).convert("RGBA")
    return _IMG[name]


def scaled(im, h):
    key = (id(im), int(h))
    if key not in _IMG:
        h = max(int(h), 2)
        _IMG[key] = im.resize((max(int(im.width * h / im.height), 2), h), Image.LANCZOS)
    return _IMG[key]


def interp(keys, t, base):
    """keys [[t, {..}]] → 그 시각 값. 키 사이는 감속(ease-out), 오버슈트 없음."""
    st = dict(base)
    if not keys:
        return st
    prev_t, prev = keys[0][0], {**base, **keys[0][1]}
    if t <= prev_t:
        return prev
    for kt, kv in keys[1:]:
        cur = {**prev, **kv}
        if t < kt:
            u = ease((t - prev_t) / max(kt - prev_t, 1e-6))
            return {k: prev[k] + (cur[k] - prev[k]) * u for k in cur}
        prev_t, prev = kt, cur
    return prev


def lerp_keys(keys, t, linear=False):
    if t <= keys[0][0]:
        return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if t < b[0]:
            u = (t - a[0]) / max(b[0] - a[0], 1e-6)
            u = u if linear else ease(u)
            return [x + (y - x) * u for x, y in zip(a[1:], b[1:])]
    return keys[-1][1:]


def paste(canvas, im, cx, cy, s=1.0, r=0.0, a=1.0, flip=False):
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if abs(s - 1) > 1e-3:
        im = im.resize((max(int(im.width * s), 1), max(int(im.height * s), 1)), Image.BILINEAR)
    if abs(r) > 0.05:
        im = im.rotate(r, resample=Image.BICUBIC, expand=True)
    if a < 0.999:
        al = im.getchannel("A").point(lambda v: int(v * a))
        im = im.copy()
        im.putalpha(al)
    canvas.alpha_composite(im, (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))


def fnt(weight, size):
    return s6.font(s6.FONT_XB if weight == "xb" else s6.FONT_B, size)


class Scene:
    def __init__(self, sc, layers, t0, t1):
        self.sc, self.layers, self.t0, self.t1 = sc, layers, t0, t1
        self.bg = load(layers, sc["bg"]) if sc.get("bg") else None

    def cam(self, t):
        keys = self.sc.get("cam") or [[0, 1.0, 0, 0], [self.t1 - self.t0, 1.06, 0, 0]]
        z, dx, dy = lerp_keys(keys, t)
        return z, dx, dy

    def draw(self, t):
        z, dx, dy = self.cam(t)
        world = Image.new("RGBA", (W, H), (20, 24, 36, 255))
        if self.bg:
            bd = self.sc.get("bg_depth", 0.5)
            bz = 1 + (z - 1) * bd
            b = self.bg.resize((int(W * bz * 1.02), int(H * bz * 1.02)), Image.BILINEAR)
            world.alpha_composite(b, (int(W / 2 - b.width / 2 + dx * bd), int(H / 2 - b.height / 2 + dy * bd)))
        for it in self.sc.get("items", []):
            if t < it.get("t0", 0) or t >= it.get("t1", 1e9):
                continue
            self.item(world, it, t, z, dx, dy)
        return world

    def place(self, x, y, depth, z, dx, dy):
        zz = 1 + (z - 1) * depth
        return W / 2 + (x - W / 2) * zz + dx * depth, H / 2 + (y - H / 2) * zz + dy * depth, zz

    def item(self, cv, it, t, z, dx, dy):
        k = it["kind"]
        lt = t - it.get("t0", 0)
        dep = it.get("depth", 1.0)
        intro = it.get("intro", 0.2)          # 등장 6프레임 감속(밀려 들어옴 + 투명→불투명)
        ia = ease(lt / intro) if intro else 1
        if k == "sprite":
            name = it["file"]
            for pt, pf in it.get("poses", []):
                if t >= pt:
                    name = pf
            st = interp(it.get("keys"), lt, {"x": it["x"], "y": it["y"], "s": 1.0, "r": 0.0, "a": 1.0})
            bob = it.get("bob")
            yb = bob[0] * math.sin(2 * math.pi * t / bob[1]) if bob else 0
            sb = 1 + (0.006 * math.sin(2 * math.pi * t / 3.1) if it.get("breathe", True) else 0)
            x, y, zz = self.place(st["x"], st["y"] + yb + (1 - ia) * it.get("rise", 40), dep, z, dx, dy)
            im = scaled(load(self.layers, name), it["h"] * zz)
            paste(cv, im, x, y, st["s"] * sb, st["r"], st["a"] * ia, it.get("flip", False))
        elif k == "stream":
            im0 = load(self.layers, it["file"])
            ev, tr = it["every"], it["travel"]
            n0 = int(math.floor((lt - tr) / ev))
            for n in range(max(n0, -int(tr / ev) - 1), int(lt / ev) + 1):
                born = n * ev
                u = (lt - born) / tr
                if not 0 <= u <= 1:
                    continue
                if born < 0 and not it.get("prefill", True):
                    continue
                rnd = (math.sin(n * 12.9898) * 43758.5453) % 1
                jx = (rnd - 0.5) * it.get("jitter", 0)
                px = it["p0"][0] + (it["p1"][0] - it["p0"][0]) * u
                py = it["p0"][1] + (it["p1"][1] - it["p0"][1]) * u - it.get("arc", 0) * math.sin(math.pi * u) + jx
                x, y, zz = self.place(px, py, dep, z, dx, dy)
                fade = min(1, u / 0.08, (1 - u) / 0.08) if it.get("fade", True) else 1
                im = scaled(im0, it["h"] * zz * (0.9 + 0.2 * rnd))
                paste(cv, im, x, y, 1, it.get("spin", 0) * (lt - born) + rnd * it.get("tilt", 0), fade * ia)
        elif k == "text":
            f = fnt(it.get("weight", "xb"), it["size"])
            txt = it["text"]
            if "count" in it:
                a, b, d = it["count"]
                v = a + (b - a) * ease(lt / d)
                txt = f"{int(round(v)):,}" + it.get("suffix", "")
            tw = f.getlength(txt)
            asc, desc = f.getmetrics()
            pad = it.get("pad", [28, 16])
            box = Image.new("RGBA", (int(tw + pad[0] * 2), asc + desc + pad[1] * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(box)
            if it.get("box"):
                d.rounded_rectangle([0, 0, box.width - 1, box.height - 1], 14, fill=tuple(it["box"]) + (255,))
            d.text((pad[0], pad[1]), txt, font=f, fill=tuple(it.get("color", [245, 245, 245])))
            x, y, zz = self.place(it["x"], it["y"] + (1 - ia) * 24, dep, z, dx, dy)
            paste(cv, box, x, y, zz, 0, ia)
        elif k == "hands":
            x, y, zz = self.place(it["x"], it["y"], dep, z, dx, dy)
            d = ImageDraw.Draw(cv)
            r = it["r"] * zz
            for frac, ln, wd in ((it["speed"], 0.78, 5), (it["speed"] / 12, 0.52, 8)):
                ang = 2 * math.pi * frac * t - math.pi / 2
                d.line([x, y, x + r * ln * math.cos(ang), y + r * ln * math.sin(ang)], fill=(40, 44, 58, 255), width=int(wd * zz))
            d.ellipse([x - 7 * zz, y - 7 * zz, x + 7 * zz, y + 7 * zz], fill=(205, 105, 50, 255))
        elif k == "fill":
            lv = lerp_keys(it["level"], lt, linear=True)[0]   # 수위는 고르게(감속하면 처음에 확 빠짐)
            rx, ry, rw, rh = it["rect"]
            src = load(self.layers, it["file"]).resize((rw, rh), Image.BILINEAR)
            cut = int(rh * (1 - lv))
            if cut < rh:
                part = src.crop((0, cut, rw, rh))
                x, y, zz = self.place(rx + rw / 2, ry + cut + (rh - cut) / 2, dep, z, dx, dy)
                paste(cv, part, x, y, zz, 0, ia)
        elif k == "card":
            card = Image.new("RGBA", (it["w"], it["h"]), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, it["w"] - 1, it["h"] - 1], 14, fill=tuple(it.get("color", [248, 244, 236])) + (255,))
            if it.get("icon"):
                ic = scaled(load(self.layers, it["icon"]), it["h"] * 0.7)
                card.alpha_composite(ic, ((it["w"] - ic.width) // 2, (it["h"] - ic.height) // 2))
            x, y, zz = self.place(it["x"], it["y"] + (1 - ia) * 30, dep, z, dx, dy)
            paste(cv, card, x, y, zz, 0, ia)
        elif k == "arrow":
            g = ease(lt / it.get("grow", 0.3))
            (x0, y0), (x1, y1) = it["p0"], it["p1"]
            x1, y1 = x0 + (x1 - x0) * g, y0 + (y1 - y0) * g
            P0 = self.place(x0, y0, dep, z, dx, dy)
            P1 = self.place(x1, y1, dep, z, dx, dy)
            d = ImageDraw.Draw(cv)
            col = tuple(it.get("color", [205, 105, 50])) + (255,)
            wd = it.get("width", 12)
            d.line([P0[0], P0[1], P1[0], P1[1]], fill=col, width=wd)
            ang = math.atan2(P1[1] - P0[1], P1[0] - P0[0])
            hl = wd * 2.6
            pts = [(P1[0] + hl * math.cos(ang), P1[1] + hl * math.sin(ang)),
                   (P1[0] + hl * 0.9 * math.cos(ang + 2.4), P1[1] + hl * 0.9 * math.sin(ang + 2.4)),
                   (P1[0] + hl * 0.9 * math.cos(ang - 2.4), P1[1] + hl * 0.9 * math.sin(ang - 2.4))]
            d.polygon(pts, fill=col)


def src_to_out(pieces, s):
    acc = 0.0
    for p in pieces:
        if p["in"] <= s <= p["out"] + 1e-6:
            return acc + s - p["in"]
        acc += p["out"] - p["in"]
    return None


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def render(plan, preview=None, stills=None):
    fps = plan.get("fps", 30)
    pieces = plan["pieces"]
    total = sum(p["out"] - p["in"] for p in pieces)
    if preview:
        total = min(total, preview)
    layers = ROOT / plan["layers"]
    scenes = []
    for sc in plan["scenes"]:
        a, b = src_to_out(pieces, sc["from"]), src_to_out(pieces, sc["to"])
        scenes.append(Scene(sc, layers, a, b))
    s6.SRC_FOR_SPLIT[:] = [plan["src"]]
    caps = []
    for c in plan.get("captions", []):
        for p in s6.split_caption(dict(c)):
            a, b = src_to_out(pieces, p["from"]), src_to_out(pieces, p["to"])
            caps.append((a, b, p["text"], p.get("hl"), s6.caption_img(p["text"], p.get("hl"))))
    out = ROOT / plan["out"]
    out.parent.mkdir(parents=True, exist_ok=True)

    def frame(t):
        sc = next((s for s in scenes if s.t0 <= t < s.t1), scenes[-1])
        cv = sc.draw(t - sc.t0)
        for a, b, _, _, im in caps:
            if a <= t < b:
                cv.alpha_composite(im, (W // 2 - im.width // 2, CAP_Y - im.height // 2))
        return cv.convert("RGB")

    if stills:
        for t in stills:
            p = out.with_name(out.name + f"_{t:05.2f}s.png")
            frame(t).save(p)
            print("정지", p)
        return

    # 목소리: 원본 구간 이어 붙이기(구간 끝 10ms 녹임 — 툭 소리 방지)
    voice = ROOT / "_tmp" / "anim2d" / (out.name + "_voice.wav")
    voice.parent.mkdir(parents=True, exist_ok=True)
    fl = ";".join(f"[0:a]atrim={p['in']}:{p['out']},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={p['out'] - p['in'] - 0.01}:d=0.01[a{i}]" for i, p in enumerate(pieces))
    fl += ";" + "".join(f"[a{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", plan["src"], "-filter_complex", fl, "-map", "[v]", "-ar", "48000", "-ac", "2", str(voice)], check=True)

    mp4 = out.with_suffix(".mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            "-i", str(voice), "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
    n = int(round(total * fps))
    still_run, last = 0, None
    for i in range(n):
        im = frame(i / fps)
        arr = np.asarray(im)
        if last is not None and np.abs(arr[::8, ::8].astype(np.int16) - last).mean() < 0.05:
            still_run += 1
            if still_run == int(fps * 0.6):
                print(f"WARN 화면 멈춤 0.6초↑ @ {i / fps:.2f}s")
        else:
            still_run = 0
        last = arr[::8, ::8].astype(np.int16)
        enc.stdin.write(arr.tobytes())
        if i % (fps * 5) == 0:
            print(f"  {i / fps:5.1f}/{total:.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    with open(out.with_suffix(".srt"), "w", encoding="utf-8", newline="\n") as f:
        for k, (a, b, txt, _, _) in enumerate(caps, 1):
            f.write(f"{k}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n")
    print("완료", mp4, f"{total:.1f}초")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    plan = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    pv = float(a[a.index("--preview") + 1]) if "--preview" in a else None
    st = [float(x) for x in a[a.index("--frames") + 1].split(",")] if "--frames" in a else None
    render(plan, pv, st)
