# -*- coding: utf-8 -*-
"""완성 영상에 «레퍼런스 쇼츠와 똑같은» 짧은 자막 — SRT(프리미어 캡션 = 글자·시각·스타일 수정 가능) + 프리미어 XML + 미리보기.

근거: 사장님 10-15 «D:\\26년 10월\\261015 여기에 들어있는 영상을 자막작업을 해야하는데 https://www.youtube.com/shorts/OVWZuG1KyV0
      여기 나오는 쇼츠랑 진짜 완전 똑같이 98%이상 똑같이 할거야 자막 세팅해주고 이걸 내가 수정할 수 있는 형태로 XML뽑아줘»
레퍼런스 실측(1080×1920 원본 프레임, `_tmp/study/ref_OVWZuG1KyV0`):
  글꼴 Noto Sans KR Bold(본고딕 계열 — ㅅ·권 모양·획 굵기 대조) · 크기 1080폭 기준 83px · 흰색 · 검은 외곽선 약 3px +
  검은 그림자(오른쪽 아래로 번진 짙은 그림자) · 한 줄 · 화면 세로 가운데(중심 y ≈ 0.503H) · 2~3어절(대개 2~8글자)씩 ·
  바뀔 때 애니메이션 없음(하드 컷, 0프레임) · 문장 끝 «.» «!» «?»는 그대로 둔다.
수정 가능한 형태: 프리미어가 FCP XML 안의 글자 클립을 편집 가능한 글자로 읽는다는 근거를 못 찾았다(10-15 조사) →
  XML = V1 영상 · A1/A2 소리 · V2 자막 그림(레퍼런스 모양 그대로, 줄마다 한 클립 — 밀고 늘리기 가능) /
  SRT = 프리미어 캡션 트랙(글자·시각·스타일 전부 수정). 둘 중 하나만 쓴다.

    python tools/ref_caption.py <영상.mp4> <words.json> <출력폴더> [--name 이름] [--fix "틀린말=고친말" ...]
출력: <이름>.srt · <이름>.xml · <이름>_자막그림/NNN.png · <이름>_미리보기.mp4 · <이름>_자막목록.txt
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from align_chars import align  # noqa: E402
from s6_render import break_cost  # noqa: E402

FONT = "C:/Windows/Fonts/NotoSansKR-VF.ttf"
REF_W = 1080
SIZE_1080 = 83          # 레퍼런스 1080폭 기준 글자 크기
STROKE_1080 = 3
SHADOW_1080 = (4, 5, 7, 0.85)   # dx, dy, 번짐, 진하기
CY = 0.503
MAX_CHARS = 6           # 공백 뺀 글자 수 — 레퍼런스 R1: 대개 1어절, 길어도 2어절(«많은 분께서» «숫자 복권보다»)
MAX_WORDS = 2
LEAD = 0.05             # 소리보다 먼저


ATTACH_NEXT = {"우리", "상담", "신청", "세팅", "계속", "이거", "안", "못", "이", "그", "저", "또", "더", "잘", "좀", "다", "꼭", "딱", "막", "제일", "가장", "너무", "정말", "진짜", "매일", "모든", "전"}
ATTACH_PREV = ("있", "없", "수 ", "수", "것", "거", "겁", "때문", "줄", "뿐", "만큼", "듯", "적", "중", "가능", "완료", "문의", "알림톡", "맞춤")   # 앞말에 붙는 보조용언·의존명사


def _len(ws):
    return sum(len(w) for w in ws)


def chunks_of(sentence):
    """문장 → 레퍼런스처럼 짧은 덩어리(대개 2~8글자). 덩어리 길이 점수 + 끊는 자리 점수의 합이 가장 작은 나누기(DP).
    끊으면 안 되는 자리: 꾸미는 말 뒤(«또 / 전화», «안 / 받으면»), 보조용언·의존명사 앞(«쓰고 / 있는데», «잡을 / 수»), break_cost 높은 곳."""
    w = sentence.split()
    n = len(w)

    def seg_cost(i, j):                       # w[i:j] 한 덩어리
        L = _len(w[i:j])
        if L > MAX_CHARS + 3 and j - i > 1:
            return 1e9
        c = 0.0
        if L > 6:
            c += (L - 6) ** 2 * 0.45
        if L < 2:
            c += 3
        if j - i > MAX_WORDS:
            c += 6 * (j - i - MAX_WORDS)
        return c

    def cut_cost(k):                          # w[k-1] | w[k] 사이를 끊을 때
        left, right = w[k - 1], w[k]
        c = 2 * max(0.0, float(break_cost(left, right)))
        if left in ATTACH_NEXT:
            c += 9
        if right.startswith(ATTACH_PREV):
            c += 20
        if len(left) > 1 and left[-1] in "나와과랑" :      # «실수나 / 누락을» — 나열은 한 덩어리
            c += 6
        if left[-1] in ".?!," or left.endswith("씩"):
            c -= 3                            # 쉼표·문장부호 뒤는 끊기 좋다
        return c

    best = [0.0] + [1e18] * n
    prev = [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(max(0, j - 4), j):
            c = best[i] + seg_cost(i, j) + (cut_cost(i) if i > 0 else 0)
            if c < best[j]:
                best[j], prev[j] = c, i
    out, j = [], n
    while j > 0:
        out.append(" ".join(w[prev[j]:j]))
        j = prev[j]
    return out[::-1]


JOIN_NEXT_WORD = {"또", "안", "못", "이", "그", "저", "다", "전", "꼭", "딱", "막", "잘", "좀", "더", "한", "할", "될", "제", "내", "이번"}
JOIN_PREV_WORD = ("수", "것", "거", "줄", "뿐", "것을", "것이", "것은", "것도", "수가", "수도")


def chunks_words(sentence):
    """어절 하나 = 자막 하나(10-15 «모든 / 직원들이 / 편하게 · 고객 / 상황을 / 기록하고», 어절 안은 절대 안 가름 —
    «있으 / 시다면» 금지). 한 글자 꾸밈말(또·안·이·다…)은 뒷말에, 의존명사(수·것…)는 앞말에 붙인다(«잡을 수»)."""
    w = sentence.split()
    out = []
    i = 0
    while i < len(w):
        cur = w[i]
        while cur.split()[-1] in JOIN_NEXT_WORD and i + 1 < len(w):
            i += 1
            cur += " " + w[i]
        if out and cur.split()[0] in JOIN_PREV_WORD:
            out[-1] += " " + cur
        else:
            out.append(cur)
        i += 1
    return out


_ENV = {}


def _envelope(wav):
    """5ms RMS(dB) — 음량이 올라오는 순간(말 시작)을 찾는 데 쓴다."""
    if wav not in _ENV:
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                             capture_output=True).stdout
        x = np.frombuffer(raw, np.int16).astype(float) / 32768
        hop = 80
        n = len(x) // hop
        e = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
        floor = float(np.percentile(e, 10))
        speech = float(np.percentile(e, 70))
        _ENV[wav] = (e, floor, speech)
    return _ENV[wav]


def refine_onset(wav, t, lo):
    """정렬 첫 음절 시각 t 를 «소리가 실제로 올라오는 점»으로 보정 — 앞쪽 0.15초 안에 조용한 틈이 있으면
    그 틈이 끝나는 점(음량이 말소리 쪽으로 올라오는 첫 5ms)으로 당긴다. 늦추지는 않는다. lo 보다 앞으로는 안 간다."""
    e, floor, speech = _envelope(wav)
    thr = floor + 0.35 * (speech - floor)
    i1 = int(t / 0.005)
    i0 = max(int(max(t - 0.15, lo) / 0.005), 0)
    if i1 <= i0 or i1 >= len(e):
        return t
    seg = e[i0:i1 + 1]
    quiet = [j for j in range(len(seg)) if seg[j] < thr]
    if not quiet:
        return t                        # 이어 말하는 중 — 정렬 시각 그대로
    j = quiet[-1] + 1                   # 마지막 조용한 칸 다음 = 말 시작
    return (i0 + j) * 0.005


def _onset_ctx(wav, caps, i, pad):
    """자막 i 의 첫 음절 — 앞뒤 자막 글을 같이 넣고 그 둘레를 정렬(문장 정렬과 다른 맥락으로 한 번 더 재기)."""
    s, e, t = caps[i][0], caps[i][1], caps[i][2]
    prev = caps[i - 1][2] if i else None
    nxt = caps[i + 1][2] if i + 1 < len(caps) else None
    texts = [x for x in (prev, t, nxt) if x]
    t0 = (caps[i - 1][0] if i else s) - pad
    t1 = (caps[i + 1][1] if nxt else e) + pad
    r = align(wav, max(t0, 0), t1, texts)[1 if prev else 0]
    if not r:
        return None
    return refine_onset(wav, r[0][1], (caps[i - 1][0] + 0.08) if i else 0)


def cross_check(wav, caps):
    """시작 시각을 맥락 셋(문장 정렬 · 앞뒤 자막 0.3초 · 앞뒤 자막 0.7초)으로 재서 가운데 값을 쓴다 —
    배경음악이 깔린 목소리는 정렬 한 번이 0.1~0.2초씩 튈 때가 있다(10-15 «신청해보세요» +0.22초)."""
    import statistics
    for i in range(len(caps)):
        a = caps[i][0]
        b = _onset_ctx(wav, caps, i, 0.3)
        if b is None or abs(a - b) <= 0.034:
            continue
        c = _onset_ctx(wav, caps, i, 0.7)
        vals = [v for v in (a, b, c) if v is not None]
        caps[i][0] = statistics.median(vals)
        if i:
            caps[i - 1][1] = caps[i][0]


def timings(wav, sentences, mode="chunk", lead=None):
    """문장마다 덩어리 첫 음절 시각을 강제 정렬로 — [(시작, 끝, 글)].
    mode="word": 어절 하나씩 + 시작을 음량 상승점으로 보정, 앞당김(lead) 기본 0(10-15 «SRT 타이밍 … 보이스랑»)."""
    lead = (0.0 if mode == "word" else LEAD) if lead is None else lead
    caps = []
    for k, s in enumerate(sentences):
        chs = (chunks_words if mode == "word" else chunks_of)(s["text"].strip())
        # 받아쓰기 문장 경계 시각은 0.4초쯤 틀린다(10-15 «클릭»이 앞 문장 «받으면»에 붙음) → 앞뒤 문장 글까지 같이 넣고
        #   앞 문장 시작 ~ 뒤 문장 끝을 통째로 정렬한 뒤 이 문장 몫만 쓴다
        pv = sentences[k - 1] if k else None
        nx = sentences[k + 1] if k + 1 < len(sentences) else None
        texts = ([pv["text"].strip()] if pv else []) + chs + ([nx["text"].strip()] if nx else [])
        rows = align(wav, max((pv or s)["start"] - 0.3, 0), (nx or s)["end"] + 0.3, texts)
        rows = rows[(1 if pv else 0):(1 if pv else 0) + len(chs)]
        starts = []
        for j, r in enumerate(rows):
            t = r[0][1] if r else None          # 숫자·영문 덩어리(#)도 그 첫 토큰 시각(«10만원씩»을 «만»에서 시작하지 않게)
            starts.append(t)
        # 못 잰 덩어리는 글자 수 비례로 메움
        for j in range(len(chs)):
            if starts[j] is None:
                a = starts[j - 1] if j else s["start"]
                starts[j] = a + 0.25
        ends = [starts[j + 1] for j in range(len(chs) - 1)] + [None]
        last = rows[-1][-1][2] if rows and rows[-1] else s["end"]
        ends[-1] = max(last + 0.15, starts[-1] + 0.4)
        if mode == "word":
            prev_end = caps[-1][0] + 0.08 if caps else 0.0
            for j in range(len(starts)):
                lo = starts[j - 1] + 0.08 if j else prev_end
                starts[j] = refine_onset(wav, starts[j], lo)
            ends = [starts[j + 1] for j in range(len(chs) - 1)] + [ends[-1]]
        for a, b, t in zip(starts, ends, chs):
            caps.append([max(a - lead, 0), b - lead, t, k])
    def settle():
        # 시작 시각은 앞 자막보다 최소 0.25초 뒤(정렬이 한 음절 거꾸로 짚는 경우)
        for i in range(1, len(caps)):
            caps[i][0] = max(caps[i][0], caps[i - 1][0] + (0.1 if mode == "word" else 0.25))
        # 다음 자막 앞까지 이어 붙이되(빈틈 0.5초 미만이면) 겹치지 않게
        for i in range(len(caps) - 1):
            nxt = caps[i + 1][0]
            if nxt - caps[i][1] < 0.5:
                caps[i][1] = nxt
            caps[i][1] = min(caps[i][1], nxt)

    settle()
    # 너무 짧게 스치는 덩어리(0.4초 미만)는 **같은 문장 안** 이웃과 합친다(합쳐 11글자 이하인 쪽, 앞 먼저)
    i = 0
    while i < len(caps):
        s0, e0, t0, k0 = caps[i]
        if e0 - s0 < (0.12 if mode == "word" else 0.32):
            pv = caps[i - 1] if i > 0 and caps[i - 1][3] == k0 else None
            nx = caps[i + 1] if i + 1 < len(caps) and caps[i + 1][3] == k0 else None
            ok_p = pv and len((pv[2] + t0).replace(" ", "")) <= 8
            ok_n = nx and len((t0 + nx[2]).replace(" ", "")) <= 8
            # 조사로 끝나는 짧은 덩어리(«부재는»)는 뒷말에, 아니면(«안 받으면») 앞말에 붙인다
            to_next = ok_n and (t0[-1] in "는은이가을를에도로" or not ok_p)
            if to_next:
                caps[i + 1] = [s0, nx[1], t0 + " " + nx[2], k0]
                caps.pop(i)
                continue
            if ok_p:
                caps[i - 1] = [pv[0], e0, pv[2] + " " + t0, k0]
                caps.pop(i)
                continue
        i += 1
    settle()
    if mode == "word":
        cross_check(wav, caps)
        settle()
    caps = [c[:3] for c in caps]
    return caps


def cap_png(text, W, H):
    k = W / REF_W
    f = ImageFont.truetype(FONT, int(SIZE_1080 * k))
    f.set_variation_by_name("Bold")
    sw = max(1, round(STROKE_1080 * k))
    dx, dy, bl, op = SHADOW_1080
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).text((W / 2 + dx * k, H * CY + dy * k), text, font=f, fill=255, anchor="mm",
                            stroke_width=sw + round(2 * k), stroke_fill=255)
    sh = sh.filter(ImageFilter.GaussianBlur(bl * k)).point(lambda v: int(v * op))
    im.paste((0, 0, 0, 255), (0, 0), sh)
    ImageDraw.Draw(im).text((W / 2, H * CY), text, font=f, fill=(255, 255, 255, 255), anchor="mm",
                            stroke_width=sw, stroke_fill=(0, 0, 0, 255))
    return im


def ts(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h:02d}:{m:02d}:{t % 60:06.3f}".replace(".", ",")


def url(p):
    return "file://localhost/" + quote(str(Path(p).resolve()).replace("\\", "/"), safe="/")


def probe(mp4):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(mp4)],
                         capture_output=True, text=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    a, b = st["r_frame_rate"].split("/")
    return st["width"], st["height"], float(a) / float(b), float(j["format"]["duration"])


def write_xml(path, name, mp4, pngs, caps, W, H, fps, dur):
    ntsc = "TRUE" if abs(fps - round(fps)) > 0.01 else "FALSE"
    tb = int(round(fps))
    fr = (lambda t: int(round(t * tb * 1000 / 1001))) if ntsc == "TRUE" else (lambda t: int(round(t * tb)))
    R = f"<rate><timebase>{tb}</timebase><ntsc>{ntsc}</ntsc></rate>"
    N = fr(dur)
    fv = (f'<file id="file-src"><name>{Path(mp4).name}</name><pathurl>{url(mp4)}</pathurl>{R}<duration>{N}</duration>'
          f'<media><video><samplecharacteristics>{R}<width>{W}</width><height>{H}</height></samplecharacteristics></video>'
          f'<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics>'
          f'<channelcount>2</channelcount></audio></media></file>')
    v1 = (f'<clipitem id="v1"><name>{Path(mp4).name}</name><enabled>TRUE</enabled><duration>{N}</duration>{R}'
          f'<start>0</start><end>{N}</end><in>0</in><out>{N}</out>{fv}'
          f'<sourcetrack><mediatype>video</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
    a = ""
    for ch in (1, 2):
        a += (f'<track><clipitem id="a{ch}"><name>{Path(mp4).name}</name><enabled>TRUE</enabled><duration>{N}</duration>{R}'
              f'<start>0</start><end>{N}</end><in>0</in><out>{N}</out><file id="file-src"/>'
              f'<sourcetrack><mediatype>audio</mediatype><trackindex>{ch}</trackindex></sourcetrack></clipitem></track>')
    v2 = ""
    for i, ((s, e, t), p) in enumerate(zip(caps, pngs), 1):
        a0, a1 = fr(s), max(fr(e), fr(s) + 1)
        L = a1 - a0
        v2 += (f'<clipitem id="cap{i}"><name>{i:03d} {t}</name><enabled>TRUE</enabled><duration>{L}</duration>{R}'
               f'<start>{a0}</start><end>{a1}</end><in>0</in><out>{L}</out>'
               f'<file id="png{i}"><name>{Path(p).name}</name><pathurl>{url(p)}</pathurl>{R}<duration>{L}</duration>'
               f'<media><video><samplecharacteristics><width>{W}</width><height>{H}</height></samplecharacteristics></video></media></file>'
               f'</clipitem>')
    seq = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="seq">'
           f'<name>{name}</name><duration>{N}</duration>{R}<media>'
           f'<video><format><samplecharacteristics>{R}<width>{W}</width><height>{H}</height>'
           f'<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></format>'
           f'<track>{v1}</track><track>{v2}</track></video>'
           f'<audio>{a}</audio></media></sequence></xmeml>\n')
    Path(path).write_text(seq, encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:]]
    mp4, words, out = Path(a[0]), Path(a[1]), Path(a[2])
    name = a[a.index("--name") + 1] if "--name" in a else mp4.stem.strip()
    fixes = [a[i + 1].split("=", 1) for i, x in enumerate(a) if x == "--fix"]
    out.mkdir(parents=True, exist_ok=True)
    W, H, fps, dur = probe(mp4)
    sents = json.loads(words.read_text(encoding="utf-8"))
    for s in sents:
        for wrong, right in fixes:
            s["text"] = s["text"].replace(wrong, right)
    wav = out / "_voice16k.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-ac", "1", "-ar", "16000", str(wav)], check=True)
    caps = timings(str(wav), sents)
    wav.unlink()
    (out / f"{name}.srt").write_text("".join(f"{i}\n{ts(s)} --> {ts(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(caps, 1)),
                                     encoding="utf-8")
    (out / f"{name}_자막목록.txt").write_text("\n".join(f"{s:6.2f}~{e:6.2f}  {t}" for s, e, t in caps) + "\n", encoding="utf-8")
    pd = out / f"{name}_자막그림"
    pd.mkdir(exist_ok=True)
    pngs = []
    for i, (s, e, t) in enumerate(caps, 1):
        p = pd / f"{i:03d}.png"
        cap_png(t, W, H).save(p)
        pngs.append(p)
    write_xml(out / f"{name}.xml", f"{name}_자막", mp4, pngs, caps, W, H, fps, dur)
    # 미리보기(확인용, 1080×1920): 자막 그림을 시각대로 얹기
    pv = out / f"{name}_미리보기.mp4"
    flt, inp = ["[0:v]scale=1080:1920[b0]"], ["-i", str(mp4)]
    for i, ((s, e, t), p) in enumerate(zip(caps, pngs), 1):
        inp += ["-i", str(p)]
        flt.append(f"[{i}:v]scale=1080:1920[c{i}];[b{i - 1}][c{i}]overlay=0:0:enable='between(t,{s:.3f},{e - 0.001:.3f})'[b{i}]")
    script = out / "_flt.txt"
    script.write_text(";".join(flt), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inp, "-filter_complex_script", str(script), "-map", f"[b{len(caps)}]",
                    "-map", "0:a", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", str(pv)],
                   check=True)
    script.unlink()
    print(f"자막 {len(caps)}줄 · {W}×{H} {fps:.2f}fps · {out}")


if __name__ == "__main__":
    main()
