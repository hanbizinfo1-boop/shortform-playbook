# -*- coding: utf-8 -*-
"""자막 + 글자 연출(레퍼런스 OVWZuG1KyV0 방식) → 층별 PNG + 프리미어 XML + SRT + 미리보기.

근거: 사장님 10-15 «내가 준 링크 속도감을 전혀못살리고 색이나 글자 계산하는 표현이라던가 그런 연출도 하나도없는데
      아까 준 링크 정독하고 수정해» — 요구 대장 `기록/레퍼해부/자막레퍼_OVWZuG1KyV0.md`(R1~R13).

    python tools/caption_fx.py <연출계획.json>

연출계획.json
  video, words(받아쓰기 words.json), out(폴더), name, fix:[["틀린","고친"]],
  fx: [ {type, on|from/to(자막 글 조각 — 그 자막의 시각에 붙는다), ...} ]
    sticker  {img(소재/ai/sticker/ 이름), on, until?}            R5 자막 바로 위 가운데
    bignum   {text, on, color:"green"}                            R3 자막 자리에 큰 기울임 숫자(그동안 자막 숨김)
    calc     {from, to, lines:[[글, 색, 붙을 자막 조각, 지연초]...]} R4 위쪽에 한 줄씩 쌓기(«__line__» = 밑줄), 그동안 자막 숨김
    label    {text, from, to}                                     R7 빨간 상자(여러 자막 동안 유지)
    arrow    {on, until?, tip:[x,y](1080 기준), angle(도, 화살 방향)} R6
    ff       {from, to}                                           R8 ▶▶ 반투명(자막 뒤)
    speed    {from, to}                                           R9 집중선(0.1초마다 바뀜)
    big      {on, scale}                                          R10 그 자막만 크게
    color    {on, color}                                          R11 그 자막 글자색
XML 트랙(아래→위): V1 영상 · V2 ▶▶·집중선 · V3 자막 · V4 스티커·라벨·화살표 · V5 큰 숫자·계산식 / A1·A2 소리.
글자 수정은 SRT(프리미어 캡션 트랙). V3 를 끄고 SRT 를 쓰면 된다.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import ref_caption as RC  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STK = ROOT / "소재" / "ai" / "sticker"
UF = "C:/Users/user/AppData/Local/Microsoft/Windows/Fonts/"
NUM_FONT = UF + "Cafe24Ssurround-v2.0.otf"      # 레퍼런스 큰 숫자(둥근 굵은 기울임)에 가장 가까움(10-15 대조)
COL = {"white": (255, 255, 255), "green": (34, 229, 30), "red": (255, 34, 34), "yellow": (255, 212, 0),
       "bgreen_top": (130, 255, 80), "bgreen_bot": (24, 214, 24)}


def noto(size):
    f = ImageFont.truetype(RC.FONT, size)
    f.set_variation_by_name("Bold")
    return f


def text_layer(W, H, text, cx, cy, size, fill, stroke, shadow=True, font=None):
    """흰(또는 색) 글자 + 검은 외곽선 + 짙은 그림자 — 레퍼런스 자막 모양을 임의 자리에."""
    k = W / RC.REF_W
    f = font or noto(int(size * k))
    sw = max(1, round(stroke * k))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow:
        dx, dy, bl, op = RC.SHADOW_1080
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).text((cx * k + dx * k, cy * k + dy * k), text, font=f, fill=255, anchor="mm",
                                stroke_width=sw + round(2 * k), stroke_fill=255)
        sh = sh.filter(ImageFilter.GaussianBlur(bl * k)).point(lambda v: int(v * op))
        im.paste((0, 0, 0, 255), (0, 0), sh)
    ImageDraw.Draw(im).text((cx * k, cy * k), text, font=f, fill=fill + (255,), anchor="mm",
                            stroke_width=sw, stroke_fill=(0, 0, 0, 255))
    return im


def caption_layer(W, H, text, scale=1.0, color="white"):
    cy = RC.CY * 1920
    return text_layer(W, H, text, 540, cy, RC.SIZE_1080 * scale, COL[color], RC.STROKE_1080)


def bignum_layer(W, H, text):
    """R3 — 초록 그라데이션 큰 기울임 숫자 + 두꺼운 검은 외곽선 + 그림자. «1,000,000» 폭 ≈ 830px(1080)."""
    k = W / 1080
    size = int(205 * k * min(1.0, 9 / max(len(text), 1)) ** 0.35)   # «1,000,000» 폭 ≈ 830px(1080) — 레퍼런스 실측
    sw = int(11 * k)
    # 키프레임으로 108%까지 커져도 화면 폭 안(가로 90% 이하)에 들어오게 줄인다(10-15 «1,000,000» 양옆 잘림)
    while True:
        f = ImageFont.truetype(NUM_FONT, size)
        bb0 = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, anchor="lt", stroke_width=sw)
        if ((bb0[2] - bb0[0]) + 0.2 * (bb0[3] - bb0[1])) * 1.08 <= W * 0.9 or size < 40:   # 기울임 폭 포함, 최대일 때 90%
            break
        size = int(size * 0.95)
    cx, cy = W / 2, H * RC.CY
    pad = int(60 * k)
    bb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, anchor="lt", stroke_width=sw)
    tw, th = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    m = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(m).text((pad, pad), text, font=f, fill=255, anchor="lt")
    ms = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(ms).text((pad, pad), text, font=f, fill=255, anchor="lt", stroke_width=sw, stroke_fill=255)
    grad = Image.new("RGB", (tw, th))
    a, b = np.array(COL["bgreen_top"], float), np.array(COL["bgreen_bot"], float)
    g = np.linspace(0, 1, th)[:, None, None]
    grad = Image.fromarray((a * (1 - g) + b * g).repeat(tw, 1).astype(np.uint8))
    tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    sh = ms.filter(ImageFilter.GaussianBlur(8 * k)).point(lambda v: int(v * 0.8))
    tile.paste((0, 0, 0, 255), (int(6 * k), int(8 * k)), sh)
    tile.paste((0, 0, 0, 255), (0, 0), ms)
    tile.paste(grad, (0, 0), m)
    shear = 0.2
    tile = tile.transform((tw + int(shear * th), th), Image.AFFINE, (1, shear, -shear * th, 0, 1, 0), Image.BICUBIC)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.paste(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)), tile)
    return im


def key_green(p):
    im = Image.open(p).convert("RGB")
    a = np.asarray(im, float)
    g = a[..., 1] - np.maximum(a[..., 0], a[..., 2])
    alpha = np.clip(255 - (g - 40) * 4, 0, 255).astype(np.uint8)
    a2 = a.copy()
    spill = g > 0
    a2[..., 1] = np.where(spill, np.maximum(a[..., 0], a[..., 2]) + np.minimum(g, 20) * 0.2, a[..., 1])   # 초록 번짐 빼기
    out = Image.fromarray(a2.astype(np.uint8)).convert("RGBA")
    out.putalpha(Image.fromarray(alpha).filter(ImageFilter.MinFilter(3)))
    bb = out.getbbox()
    return out.crop(bb) if bb else out


def sticker_layer(W, H, name, h1080=300):
    k = W / 1080
    st = key_green(STK / f"{name}.png")
    h = int(h1080 * k)
    st = st.resize((int(st.width * h / st.height), h), Image.LANCZOS)
    cap_top = H * RC.CY - 52 * k
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im.paste(st, (int(W / 2 - st.width / 2), int(cap_top - st.height + 30 * k)), st)
    return im


def label_layer(W, H, text):
    """R7 — 빨간 상자 + 흰 글자, 자막 바로 위(아랫변이 자막 윗변에 살짝 겹침)."""
    k = W / 1080
    f = noto(int(74 * k))
    bb = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, anchor="lt")
    bw, bh = max(int(400 * k), bb[2] - bb[0] + int(120 * k)), int(150 * k)
    x0 = int(W / 2 - bw / 2)
    y1 = int(H * RC.CY - 30 * k)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([x0 + 6 * k, y1 - bh + 8 * k, x0 + bw + 6 * k, y1 + 8 * k], fill=150)
    im.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(8 * k)))
    d.rectangle([x0, y1 - bh, x0 + bw, y1], fill=(226, 18, 18, 255))
    d.text((W / 2, y1 - bh / 2 - 4 * k), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
    return im


def arrow_layer(W, H, tip, angle):
    """R6 — 빨간 굵은 화살표(검은 테두리). tip=끝점(1080 기준), angle=화살이 가리키는 방향(0=오른쪽, 90=아래)."""
    k = W / 1080
    L, sw, hw, hl = 210 * k, 46 * k, 120 * k, 95 * k
    pts = [(0, -sw / 2), (L - hl, -sw / 2), (L - hl, -hw / 2), (L, 0), (L - hl, hw / 2), (L - hl, sw / 2), (0, sw / 2)]
    a = math.radians(angle)
    tx, ty = tip[0] * k, tip[1] * k
    P = [(tx + (x - L) * math.cos(a) - y * math.sin(a), ty + (x - L) * math.sin(a) + y * math.cos(a)) for x, y in pts]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon(P, fill=(230, 20, 20, 255))
    d.line(P + [P[0]], fill=(0, 0, 0, 255), width=int(7 * k), joint="curve")
    return im


def ff_layer(W, H):
    """R8 — ▶▶ 반투명 흰 삼각형 두 개(자막 뒤)."""
    k = W / 1080
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy, s = H * RC.CY, 300 * k
    for cx in (W / 2 - 150 * k, W / 2 + 120 * k):
        d.polygon([(cx - s / 2, cy - s / 2), (cx + s / 2, cy), (cx - s / 2, cy + s / 2)], fill=(245, 245, 245, 150))
    return im.filter(ImageFilter.GaussianBlur(1.2 * k))


def speed_layer(W, H, seed):
    """R9 — 화면 가장자리 흰 집중선(가운데는 비움)."""
    rng = np.random.default_rng(seed)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = W / 2, H * 0.5
    R = math.hypot(W, H) / 2
    for _ in range(46):
        a = rng.uniform(0, 2 * math.pi)
        r0 = R * rng.uniform(0.62, 0.8)
        w = rng.uniform(4, 14) * W / 1080
        x1, y1 = cx + R * math.cos(a), cy + R * math.sin(a)
        x0, y0 = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        d.polygon([(x0, y0), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny)], fill=(255, 255, 255, 190))
    return im


def calc_lines(W, H, lines):
    """R4 — 위쪽에 쌓는 줄 그림들(줄마다 따로) — 레퍼런스 y(1080 기준): 575 · 740 · 밑줄 855 · 960."""
    k = W / 1080
    ys = [575, 740, 855, 960]
    out = []
    for i, (txt, col, _, _) in enumerate(lines):
        y = ys[min(i, 3)]
        if txt == "__line__":
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            sh = Image.new("L", (W, H), 0)
            ImageDraw.Draw(sh).rectangle([200 * k + 5 * k, y * k - 5 * k + 6 * k, 880 * k + 5 * k, y * k + 5 * k + 6 * k], fill=170)
            im.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(5 * k)))
            d.rectangle([200 * k, y * k - 5 * k, 880 * k, y * k + 5 * k], fill=(250, 250, 250, 255))
            out.append(im)
        else:
            out.append(text_layer(W, H, txt, 540, y, 140, COL[col], 4))
    return out


# 움직임 키프레임(10-15 사장님 «v2로 그 움직임 키프레임 자막같은거에 적용시켜서 해봐») — 계획 "motion": true 일 때.
#   XML 에 Basic Motion 크기 · Opacity · Crop 키프레임으로 넣는다(프리미어에서 그대로 보이고 고칠 수 있게).
#   위치(center) 키프레임은 쓰지 않는다 — 프리미어에서 화면 밖으로 나감(쇼츠광고 강의편집 09-23 실측).
#   크기 기준점 = 화면 가운데(자막·큰 숫자·라벨은 가운데라 제자리에서 튐, 계산식 줄은 가운데 쪽에서 살짝 밀려 들어옴).
#   값: (초, 값) — 끝(-1)은 클립 끝.
ANIM = {
    "cap":   {"scale": [(0, 70), (0.05, 112), (0.1, 100)], "opacity": [(0, 0), (0.034, 100)]},
    "num":   {"scale": [(0, 0), (0.1, 130), (0.18, 100), (-1, 108)], "opacity": [(0, 0), (0.05, 100)]},
    "calc":  {"scale": [(0, 60), (0.07, 108), (0.13, 100)], "opacity": [(0, 0), (0.05, 100)]},
    "line":  {"crop_right": [(0, 81.5), (0.15, 0)]},
    "label": {"scale": [(0, 0), (0.08, 118), (0.14, 100)]},
    "ff":    {"opacity": [(0, 0), (0.08, 100)]},
}


def anim_kind(tr, nm):
    if tr == 3:
        return "cap"
    if nm.startswith("큰숫자"):
        return "num"
    if nm == "계산 __line__":
        return "line"
    if nm.startswith("계산"):
        return "calc"
    if nm.startswith("라벨"):
        return "label"
    if nm.startswith("빨리감기"):
        return "ff"
    return None


def anim_value(keys, t, dur):
    ks = [(dur if k < 0 else k, v) for k, v in keys]
    if t <= ks[0][0]:
        return ks[0][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t0 <= t <= t1:
            q = (t - t0) / max(t1 - t0, 1e-6)
            return v0 + (v1 - v0) * q
    return ks[-1][1]


def find_cap(caps, frag, after=-1.0):
    for i, (s, e, t) in enumerate(caps):
        if s >= after - 1e-3 and frag in t:
            return i
    for i, (s, e, t) in enumerate(caps):
        if frag in t:
            return i
    raise KeyError(f"자막에서 «{frag}»를 못 찾음")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    mp4, out, name = Path(plan["video"]), Path(plan["out"]), plan["name"]
    out.mkdir(parents=True, exist_ok=True)
    W, H, fps, dur = RC.probe(mp4)
    sents = json.loads(Path(plan["words"]).read_text(encoding="utf-8"))
    for s in sents:
        for wrong, right in plan.get("fix", []):
            s["text"] = s["text"].replace(wrong, right)
    wav = out / "_voice16k.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-ac", "1", "-ar", "16000", str(wav)], check=True)
    caps = RC.timings(str(wav), sents, plan.get("split", "chunk"))
    wav.unlink()

    style = {}           # 자막 번호 → (scale, color)
    hidden = set()       # 자막 숨김(큰 숫자·계산식 동안)
    layers = []          # (트랙, 시작, 끝, 이름, 그림)
    for fx in plan["fx"]:
        ty = fx["type"]
        if ty in ("big", "color"):
            i = find_cap(caps, fx["on"])
            sc, co = style.get(i, (1.0, "white"))
            style[i] = (fx.get("scale", sc), fx.get("color", co))
            continue
        after = caps[find_cap(caps, fx["after"])][0] if fx.get("after") else -1.0
        if "on" in fx:
            i0 = i1 = find_cap(caps, fx["on"], after)
            if fx.get("until"):
                i1 = find_cap(caps, fx["until"], caps[i0][0])
        else:
            i0 = find_cap(caps, fx["from"], after)
            i1 = find_cap(caps, fx["to"], caps[i0][0])
        t0, t1 = caps[i0][0], caps[i1][1]
        if ty == "sticker" and not (STK / f"{fx['img']}.png").exists():
            print(f"  (스티커 {fx['img']} 아직 없음 — 건너뜀)")
            continue
        if ty == "sticker":
            layers.append((4, t0, t1, f"스티커 {fx['img']}", sticker_layer(W, H, fx["img"], fx.get("h", 300))))
        elif ty == "bignum":
            layers.append((5, t0, t1, f"큰숫자 {fx['text']}", bignum_layer(W, H, fx["text"])))
            hidden.update(range(i0, i1 + 1))
        elif ty == "label":
            layers.append((4, t0, t1, f"라벨 {fx['text']}", label_layer(W, H, fx["text"])))
        elif ty == "arrow":
            if plan.get("motion"):
                # 위치 키프레임을 못 쓰니 두 자리(화살 방향으로 0·−28px)를 0.15초마다 번갈아 — 톡톡 찌르는 움직임
                a_ = math.radians(fx["angle"])
                far = [fx["tip"][0] - 28 * math.cos(a_), fx["tip"][1] - 28 * math.sin(a_)]
                ims = [arrow_layer(W, H, far, fx["angle"]), arrow_layer(W, H, fx["tip"], fx["angle"])]
                t, n = t0, 0
                while t < t1 - 1e-3:
                    layers.append((4, t, min(t + 0.15, t1), f"화살표{n % 2}", ims[n % 2]))
                    t += 0.15
                    n += 1
            else:
                layers.append((4, t0, t1, "화살표", arrow_layer(W, H, fx["tip"], fx["angle"])))
        elif ty == "ff":
            layers.append((2, t0, t1, "빨리감기", ff_layer(W, H)))
        elif ty == "speed":
            t, n = t0, 0
            while t < t1 - 1e-3:
                layers.append((2, t, min(t + 0.1, t1), f"집중선{n % 4}", speed_layer(W, H, n % 4)))
                t += 0.1
                n += 1
        elif ty == "calc":
            ims = calc_lines(W, H, fx["lines"])
            for (txt, col, frag, delay), im in zip(fx["lines"], ims):
                s0 = caps[find_cap(caps, frag, t0)][0] + (delay or 0)
                layers.append((5, s0, t1, f"계산 {txt}", im))
            hidden.update(range(i0, i1 + 1))

    # 자막 그림
    pd = out / f"{name}_층"
    pd.mkdir(exist_ok=True)
    for f in pd.glob("*.png"):
        f.unlink()
    clips = []           # (트랙, 시작, 끝, 이름, png)
    for i, (s, e, t) in enumerate(caps):
        if i in hidden:
            continue
        sc, co = style.get(i, (1.0, "white"))
        p = pd / f"V3_{i + 1:03d}.png"
        caption_layer(W, H, t, sc, co).save(p)
        clips.append((3, s, e, f"{i + 1:03d} {t}", p))
    cache = {}
    for j, (tr, s, e, nm, im) in enumerate(layers):
        key = nm if nm.startswith(("집중선", "화살표")) else None
        if key and key in cache:
            p = cache[key]
        else:
            p = pd / f"V{tr}_{j:03d}.png"
            im.save(p)
            if key:
                cache[key] = p
        clips.append((tr, s, e, nm, p))
    # SRT(자막만, 숨긴 줄 포함 — 수정용 원문)
    (out / f"{name}.srt").write_text("".join(f"{i}\n{RC.ts(s)} --> {RC.ts(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(caps, 1)),
                                     encoding="utf-8")
    (out / f"{name}_자막목록.txt").write_text("\n".join(f"{s:6.2f}~{e:6.2f}  {t}{'  (숨김: 큰 숫자·계산식)' if i in hidden else ''}"
                                                       for i, (s, e, t) in enumerate(caps)) + "\n", encoding="utf-8")
    motion = bool(plan.get("motion"))
    write_xml(out / f"{name}.xml", f"{name}_자막연출", mp4, clips, W, H, fps, dur, motion)
    preview(out / f"{name}_미리보기.mp4", mp4, clips, motion=motion)
    print(f"자막 {len(caps)}줄(숨김 {len(hidden)}) · 연출 층 {len(layers)}개 · {out}")


def motion_filters(kind, L, fr):
    """클립 길이 L(프레임) 안의 키프레임 필터 XML."""
    if not kind:
        return ""
    A = ANIM[kind]
    dur_s = L / fr(1.0)

    def kf(keys):
        return "".join(f"<keyframe><when>{min(int(round(fr(dur_s if t < 0 else t))), L)}</when><value>{v:.2f}</value></keyframe>"
                       for t, v in keys)
    head = ("<effectcategory>motion</effectcategory><effecttype>motion</effecttype><mediatype>video</mediatype>"
            "<pproBypass>false</pproBypass>")
    out = ""
    if "scale" in A:
        out += ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid>" + head +
                '<parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name>'
                f'<valuemin>0</valuemin><valuemax>1000</valuemax><value>100</value>{kf(A["scale"])}</parameter></effect></filter>')
    if "opacity" in A:
        out += ("<filter><effect><name>Opacity</name><effectid>opacity</effectid>" + head +
                '<parameter authoringApp="PremierePro"><parameterid>opacity</parameterid><name>opacity</name>'
                f'<valuemin>0</valuemin><valuemax>100</valuemax><value>100</value>{kf(A["opacity"])}</parameter></effect></filter>')
    if "crop_right" in A:
        out += ("<filter><effect><name>Crop</name><effectid>crop</effectid>" + head +
                '<parameter authoringApp="PremierePro"><parameterid>right</parameterid><name>right</name>'
                f'<valuemin>0</valuemin><valuemax>100</valuemax><value>0</value>{kf(A["crop_right"])}</parameter></effect></filter>')
    return out


def write_xml(path, name, mp4, clips, W, H, fps, dur, motion=False):
    ntsc = "TRUE" if abs(fps - round(fps)) > 0.01 else "FALSE"
    tb = int(round(fps))
    fr = (lambda t: int(round(t * tb * 1000 / 1001))) if ntsc == "TRUE" else (lambda t: int(round(t * tb)))
    R = f"<rate><timebase>{tb}</timebase><ntsc>{ntsc}</ntsc></rate>"
    N = fr(dur)
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fv = (f'<file id="file-src"><name>{esc(mp4.name)}</name><pathurl>{RC.url(mp4)}</pathurl>{R}<duration>{N}</duration>'
          f'<media><video><samplecharacteristics>{R}<width>{W}</width><height>{H}</height></samplecharacteristics></video>'
          f'<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics>'
          f'<channelcount>2</channelcount></audio></media></file>')
    tracks = {1: [f'<clipitem id="v1"><name>{esc(mp4.name)}</name><enabled>TRUE</enabled><duration>{N}</duration>{R}'
                  f'<start>0</start><end>{N}</end><in>0</in><out>{N}</out>{fv}'
                  f'<sourcetrack><mediatype>video</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>']}
    files = {}
    for n, (tr, s, e, nm, p) in enumerate(sorted(clips, key=lambda c: (c[0], c[1])), 1):
        a0, a1 = fr(s), max(fr(e), fr(s) + 1)
        L = a1 - a0
        new = str(p) not in files
        fid = files.setdefault(str(p), f"png{len(files) + 1}")
        fe = (f'<file id="{fid}"><name>{p.name}</name><pathurl>{RC.url(p)}</pathurl>{R}<duration>{N}</duration>'
              f'<media><video><samplecharacteristics><width>{W}</width><height>{H}</height></samplecharacteristics></video></media></file>'
              if new else f'<file id="{fid}"/>')
        tracks.setdefault(tr, []).append(
            f'<clipitem id="c{n}"><name>{esc(nm)}</name><enabled>TRUE</enabled><duration>{L}</duration>{R}'
            f'<start>{a0}</start><end>{a1}</end><in>0</in><out>{L}</out>{fe}'
            f'{motion_filters(anim_kind(tr, nm), L, fr) if motion else ""}</clipitem>')
    vt = "".join(f"<track>{''.join(tracks.get(t, []))}</track>" for t in range(1, max(tracks) + 1))
    at = "".join(f'<track><clipitem id="a{c}"><name>{esc(mp4.name)}</name><enabled>TRUE</enabled><duration>{N}</duration>{R}'
                 f'<start>0</start><end>{N}</end><in>0</in><out>{N}</out><file id="file-src"/>'
                 f'<sourcetrack><mediatype>audio</mediatype><trackindex>{c}</trackindex></sourcetrack></clipitem></track>'
                 for c in (1, 2))
    Path(path).write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="seq"><name>{esc(name)}</name>'
        f'<duration>{N}</duration>{R}<media><video><format><samplecharacteristics>{R}<width>{W}</width><height>{H}</height>'
        f'<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>'
        f'{vt}</video><audio>{at}</audio></media></sequence></xmeml>\n', encoding="utf-8")


def apply_anim(im, kind, t, dur):
    """미리보기용 — XML 키프레임과 같은 계산(크기: 화면 가운데 기준 · 불투명도 · 오른쪽 자르기)."""
    A = ANIM[kind]
    if "crop_right" in A:
        r = anim_value(A["crop_right"], t, dur) / 100
        x = int(im.width * (1 - r))
        if x < im.width:
            im = im.copy()
            im.paste((0, 0, 0, 0), (x, 0, im.width, im.height))
    if "scale" in A:
        sc = anim_value(A["scale"], t, dur) / 100
        if sc <= 0.01:
            return None
        if abs(sc - 1) > 1e-3:
            w, h = int(im.width * sc), int(im.height * sc)
            small = im.resize((w, h), Image.BILINEAR)
            if sc < 1:
                base = Image.new("RGBA", im.size, (0, 0, 0, 0))
                base.alpha_composite(small, ((im.width - w) // 2, (im.height - h) // 2))
                im = base
            else:
                cx, cy = (w - im.width) // 2, (h - im.height) // 2
                im = small.crop((cx, cy, cx + im.width, cy + im.height))
    if "opacity" in A:
        op = anim_value(A["opacity"], t, dur) / 100
        if op < 0.999:
            a = im.split()[3].point(lambda v: int(v * op))
            im = im.copy()
            im.putalpha(a)
    return im


def preview(pv, mp4, clips, fps=30, motion=False):
    """확인용 1080×1920 30fps — 원본을 줄여 읽고 그 시각에 켜진 층을 파이썬에서 얹어 다시 굽는다.
    (10-15: ffmpeg 에 4K 그림 수십 장을 한꺼번에 물리면 메모리 29GB — 미리보기가 안 끝났다)"""
    W2, H2 = 1080, 1920
    dur = RC.probe(mp4)[3]
    cache = {}
    for c in clips:
        if c[4] not in cache:
            cache[c[4]] = Image.open(c[4]).convert("RGBA").resize((W2, H2), Image.LANCZOS)
    order = sorted(clips, key=lambda c: (c[0], c[1]))
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},scale={W2}:{H2}", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    vtmp = pv.with_suffix(".v.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W2}x{H2}", "-r", str(fps),
                            "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(vtmp)],
                           stdin=subprocess.PIPE)
    n = 0
    while True:
        raw = dec.stdout.read(W2 * H2 * 3)
        if len(raw) < W2 * H2 * 3:
            break
        t = n / fps
        fr = Image.frombytes("RGB", (W2, H2), raw).convert("RGBA")
        for tr, s0, e0, nm, p in order:
            if s0 <= t < e0:
                im = cache[p]
                kind = anim_kind(tr, nm) if motion else None
                if kind:
                    im = apply_anim(im, kind, t - s0, e0 - s0)
                if im is not None:
                    fr.alpha_composite(im)
        enc.stdin.write(fr.convert("RGB").tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vtmp), "-i", str(mp4), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(pv)], check=True)
    vtmp.unlink()


if __name__ == "__main__":
    main()
