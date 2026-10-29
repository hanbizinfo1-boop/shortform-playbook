# -*- coding: utf-8 -*-
"""S6 쇼츠 점검기 — 렌더 결과(mp4)와 계획(JSON)을 대조해 «사람이 보고 듣고 걸릴 곳»을 숫자로 찾는다.

    python tools/s6_check.py <계획.json> [<완성.mp4>]      # mp4 를 안 주면 계획의 out + .mp4

근거(사장님 10-13 01편 반려): «말이 좀 끊기고 … 말을 하다가 끊기는 부분들» · «7초부분 전환효과 부자연스러운곳도있음
이런거 검사하는 검사장치하나도 만들어두면 좋을듯» · «효과음도 적절하게 들어가있는 느낌은 아님» · «마지막에 얼굴나오는건 하지마»
검사 항목
  A 잇는 곳 말 끊김   : 조각 끝·시작 60ms 가 말소리 크기인지(원본) / 단어가 자르는 점에 걸치는지(전사)
  B 숨 없이 붙음      : 출력에서 잇는 곳 앞뒤 무음 길이 < 0.15초
  C 전환 잔상         : 출력 컷 직후 0.1~0.5초에 화면이 또 크게 바뀜(원본 쪽 전환 효과가 따라 들어온 것) · 튀는 한 프레임
  D 자막              : 0.6초 미만(인지 텀) · 자막 사이 빈칸 > 0.4초 · 16자 초과
  E 효과음            : 0.12초 안에 겹침 · 같은 파일 3초 안 반복 · 3초 사슬 안 3개 초과 · 큐가 없거나 rel 미지정
  F 끝                : 마지막 말이 잘렸는지 · 엔딩 카드가 남았는지
  S 소리만·화면 없음  : 원본 화면 변화 순간(구운 효과음 자리)에 출력 화면 변화가 없음
  S2 자른 영역 밖 변화: 원본에서 잘라 내지 않은 곳(카드·칩)이 바뀌는데 출력엔 변화 없음 → 그 효과음만 남음
  H 화면 멈춤         : 내용 칸이 0.5초 이상 거의 안 바뀜(0.8초 이상 ERROR)
  G 음량              : 통합 LUFS(−14±1) · 트루피크(≤ −1.0)
  D2 자막 싱크(완성본): 완성본 소리에 자막 글자를 강제 정렬(wav2vec2 한국어) — 첫 음절보다 0.15초↑ 늦게 뜨면 ERROR
                        (10-14 «자막이랑 목소리 나오는 타이밍 정확도도 너무낮은데»)
  K 자료 잘림         : 자료(화면녹화·그림) 위·아래 끝이 글자·카드 한가운데를 가르는지 · 가장자리 검은 띠 — ERROR (10-14 «위아래가 너무잘려있고»)
  E4 효과음 결        : 통과 효과음과 소리 모양이 먼 파일 WARN (`sfx_feel.py`, 10-15)
  E3 효과음 반복      : 한 편 같은 파일 3회↑ ERROR · 연달아 같은 파일 WARN (10-14 «효과음 그냥 너무 반복되는데?»)
  E2 효과음 짝        : 우리가 넣은 효과음마다 화면 변화(자막 띠 제외)가 있는지 (10-14 «화면은정지인데 효과음은 띠링?»)
  M 빈 곳 표시        : 표시(밑줄·상자·동그라미)를 그릴 자리에 글자·값이 아직 없음 — 렌더러 기록 (10-14 «동그라미가 이렇게 먼저나오는건»)
  L 자막 겹침         : 자막 상자 위·아래·옆에 자료 글자가 걸림 (10-14 «레이아웃겹»)
  D3 자막 나누기      : 명사+명사·꾸미는 말+받는 말 사이에서 나눔 (10-14 «인스턴트 양식 / 같은 경우에는 이렇게 잘라야지»)
  ※ 화면 변화는 자막 띠를 빼고 잰다(H 멈춤·S 소리만 포함) — 자막이 바뀌는 걸 화면 변화로 세지 않는다
  R 글자 크기        : 자막 위 자료 글자(80분위) 36px 미만 화면이 25% 넘음 — ERROR (10-14 «3편은 모자이크 떡칠»)
  P 가림 떡칠        : 한 화면 가림 4개↑ · 한 편 5개↑ — ERROR, 실화면 대신 다시 그린 화면
  Q 안개(녹임)        : 자료 끝 페이드 사용 — ERROR (10-14 «위아래 안개낀것같은느낌»)
  T 키프레임 영상대체 : 팬 이동 2번↑ · 확대 키 8초에 1번 초과 — ERROR (10-14 «키프레임만으로 영상대체하려는 이상한 행동»)
  N 업체명·번호 노출  : 화면 글자 OCR — 실제 업체명·전화번호(○○·010-0000-0000 아님)가 보이면 ERROR (CLAUDE.md 4)
결과: «문제 N건» 목록(ERROR/WARN). ERROR 가 0 이어야 납품.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s6_render import Timeline, TOP, BOT, CAP_Y, VP, FADE_OK, PIP_CIRCLE, shot_for  # noqa: E402

W_SMALL, H_SMALL = 108, 192


def pcm(path, ss=None, t=None, sr=16000):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{ss:.3f}", "-t", f"{t:.3f}"] if ss is not None else []) + \
          ["-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.int16).astype(float) / 32768


def rms_db(x, win):
    n = max(1, len(x) // win)
    x = x[:n * win].reshape(n, win)
    return 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-9)


BLOCK_D = None   # 출력 칸(블록)별 변화 최댓값 — video_diffs 가 채운다


def video_diffs(mp4, top=TOP, bot=BOT):
    """출력 내용 칸 프레임 차이(평균). **자막 띠 줄은 뺀다** — 자막이 바뀌는 것을 화면 변화로 세면
    «소리만 나고 화면은 정지»를 놓친다(10-14 04편 «넘어갈 수 있다보니까 에 화면은정지인데 효과음은 띠링?»).
    BLOCK_D 에 칸(12×16) 최댓값도 남긴다 — 작은 글씨 하나 나타나는 변화도 잡으려고."""
    global BLOCK_D
    cmd = ["ffmpeg", "-v", "error", "-i", str(mp4), "-vf",
           f"crop=1080:{bot - top}:0:{top},scale={W_SMALL}:{H_SMALL},format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H_SMALL, W_SMALL).astype(float)
    b0 = int((CAP_Y - 80 - top) / (bot - top) * H_SMALL)
    b1 = int((CAP_Y + 80 - top) / (bot - top) * H_SMALL) + 1
    keep = np.r_[0:b0, b1:H_SMALL]
    dd = np.abs(np.diff(f[:, keep, :], axis=0))
    hh = len(keep) // 12 * 12
    blk = dd[:, :hh, :W_SMALL // 9 * 9].reshape(len(dd), 12, hh // 12, 9, W_SMALL // 9).mean((2, 4))
    BLOCK_D = blk.max((1, 2))
    global FRAMES_K
    FRAMES_K = f[:, keep, :hh][:, :, :W_SMALL // 9 * 9]        # 자막 띠 뺀 작은 프레임(창 비교용)
    return dd.mean((1, 2))      # d[i] = frame i+1 − frame i


FRAMES_K = None


def window_change(t, fps, before=0.1, after=0.4):
    """t 앞(−before)과 뒤(+after) 프레임을 통째로 비교한 칸(12×9) 최댓값 — 0.3초에 걸쳐 그려지는 밑줄도 잡는다."""
    if FRAMES_K is None:
        return 9.0
    a = max(int((t - before) * fps), 0)
    b = min(int((t + after) * fps), len(FRAMES_K) - 1)
    if b <= a:
        return 0.0
    df = np.abs(FRAMES_K[b] - FRAMES_K[a])
    hh, ww = df.shape
    return float(df[:hh // 12 * 12].reshape(12, hh // 12, 9, ww // 9).mean((1, 3)).max())


def source_diffs(src, pieces, fps=30, w=192, h=108):
    """원본 쓰는 구간의 화면 변화 순간 [(원본 초, 차이)] — 지역 최댓값이고 주변 중앙값의 4배 이상인 것."""
    ev = []
    for a, b, o in pieces:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src,
                              "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(float)
        m = np.ones((h, w), bool)
        m[int(h * 960 / 1080):, :] = False                       # 구운 자막 띠
        m[int(h * 740 / 1080):, :int(w * 340 / 1920)] = False    # PIP 원
        dd = np.array([np.abs(f[i + 1] - f[i])[m].mean() for i in range(len(f) - 1)])
        base = np.median(dd) + 0.05
        for i in range(1, len(dd) - 1):
            if dd[i] >= dd[i - 1] and dd[i] >= dd[i + 1] and dd[i] > 4 * base and dd[i] > 1.0:
                ev.append((a + (i + 1) / fps, float(dd[i])))
        # 작은 글씨 하나가 서서히 나타나는 변화(전체 평균·프레임 차이엔 안 잡힘 — 04편 «넘어감» 464.6):
        #   8프레임(0.27초) 떨어진 두 프레임의 12×9 칸 중 최댓값
        L = 8
        if len(f) > L + 2:
            df = np.abs(f[L:] - f[:-L]) * m[None]
            bk = df[:, :h // 9 * 9, :w // 12 * 12].reshape(len(df), 9, h // 9, 12, w // 12).mean((2, 4)).max((1, 2))
            for i in range(1, len(bk) - 1):
                if bk[i] >= bk[i - 1] and bk[i] >= bk[i + 1] and bk[i] > 5:
                    ev.append((a + (i + L / 2) / fps, float(bk[i]) / 10))
    # 0.3초 안에 몰린 것은 하나로(가장 큰 것)
    out = []
    for t, v in ev:
        if out and t - out[-1][0] < 0.3:
            if v > out[-1][1]:
                out[-1] = (t, v)
        else:
            out.append((t, v))
    return out


def outside_changes(plan, tl, fps=30, w=192, h=108, lag=6):
    """graphic·freeze 샷 구간에서 «쓰지 않는 원본 영역»의 0.2초 간격 변화 봉우리 [(원본 초, 값)]."""
    ev = []
    sx, sy = w / 1920, h / 1080
    for sh in plan["shots"]:
        if sh["kind"] not in ("graphic",):
            continue
        a = max(sh["from"], tl.p[0][0])
        b = min(sh["to"], tl.p[-1][1])
        if b <= a:
            continue
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", plan["src"],
                              "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(float)
        m = np.ones((h, w), bool)
        m[int(h * 960 / 1080):, :] = False
        m[int(h * 740 / 1080):, :int(w * 340 / 1920)] = False
        for rect in [sh["crop"]] + ([sh["header"]] if sh.get("header") else []) + [o["crop"] for o in sh.get("overlays", [])]:
            x, y, rw, rh = rect
            m[int(y * sy):int((y + rh) * sy) + 1, int(x * sx):int((x + rw) * sx) + 1] = False
        if m.sum() < 50:
            continue
        dd = np.array([np.abs(f[i + lag] - f[i])[m].mean() for i in range(len(f) - lag)])
        for i in range(1, len(dd) - 1):
            if dd[i] >= dd[i - 1] and dd[i] >= dd[i + 1] and dd[i] > 1.5:
                t = a + (i + lag / 2) / fps
                if not ev or t - ev[-1][0] > 0.4:
                    ev.append((t, float(dd[i])))
    return ev


def read_srt(path):
    def ts(x):
        h, m, r = x.split(":")
        sec, ms = r.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000
    out = []
    for b in Path(path).read_text(encoding="utf-8").strip().split(chr(10) * 2):
        L = b.split(chr(10))
        a, c = L[1].split(" --> ")
        out.append((ts(a), ts(c), " ".join(L[2:])))
    return out


def check_sync(mp4, add):
    """D2 — 완성본 소리에 화면 자막(.srt) 글자를 강제 정렬(align_chars) → 자막마다 첫 음절 시각과 비교.
    0.15초↑ 늦게 뜨면 ERROR, 0.4초↑ 먼저 뜨면 WARN. 숫자·영문으로 시작하는 자막은 정렬이 흔들려 WARN 만."""
    from align_chars import align
    srt = mp4.with_suffix(".srt")
    if not srt.exists():
        add("ERROR", "자막 싱크", "srt 없음")
        return
    caps = read_srt(srt)
    # 자막 하나마다 앞뒤 자막을 같이 정렬한다(앞뒤 글자가 닻) — 긴 덩어리로 한 번에 하면 경계에서 한 음절씩 밀렸다
    #   (10-14: 25초 덩어리 → 03편 «데이터가»를 앞 «아니라»의 «라»로, 10초 덩어리 → 다른 경계가 0.4초 밀림)
    for k, (a, b, t) in enumerate(caps):
        ks = [x for x in (k - 1, k, k + 1) if 0 <= x < len(caps) and abs(caps[x][0] - a) < 6]
        t0 = max(caps[ks[0]][0] - 0.4, 0)
        t1 = caps[ks[-1]][1] + 0.4
        rows = align(str(mp4), t0, t1, [caps[x][2] for x in ks])
        row = rows[ks.index(k)]
        if not row:
            add("WARN", f"{a:.2f}s 자막", f"«{t}» 정렬 못 함")
            continue
        v = row[0][1]
        late = a - v
        if row[0][0] == "#":
            if abs(late) > 0.4:
                add("WARN", f"{a:.2f}s 자막", f"«{t}» 숫자로 시작 — 정렬상 {late:+.2f}초(귀로 확인)")
            continue
        if late > 0.15:
            add("ERROR", f"{a:.2f}s 자막", f"«{t}» 첫 음절({v:.2f})보다 {late:.2f}초 늦게 뜸")
        elif late < -0.4:
            add("WARN", f"{a:.2f}s 자막", f"«{t}» 첫 음절({v:.2f})보다 {-late:.2f}초 먼저 뜸")
        if b < row[-1][1] - 0.2:
            add("WARN", f"{a:.2f}s 자막", f"«{t}» 마지막 음절을 말하기 전에 사라짐({row[-1][1] - b:.2f}초)")


def check_cut(plan, tl, mp4, add, step=0.25):
    """K — 자료 칸(graphic·pan·freeze)에서 내용 덩어리의 위·아래 끝이 글자줄을 가르는지(끝 3줄의 글자 밀도)."""
    from PIL import Image
    dur = tl.dur
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf",
                          f"fps={1 / step},crop=1080:{BOT - TOP}:0:{TOP},format=rgb24", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, BOT - TOP, 1080, 3).astype(float)
    cap0, cap1 = CAP_Y - 80 - TOP, CAP_Y + 80 - TOP
    hits = []
    for i in range(len(fr)):
        t = (i + 0.5) * step
        if t >= dur or tl.in_gap(t):
            continue
        sv = tl.to_src(t)
        if sv is None:
            continue
        sh = shot_for(plan, sv)
        if sh["kind"] not in ("graphic", "pan", "freeze"):
            continue
        f = fr[i]
        g = f.mean(2)
        det = np.abs(np.diff(g, axis=1)).mean(1)
        flat_bg = not (sh["kind"] == "pan" and sh.get("bg_blur", True))
        if flat_bg:
            bg = np.array(sh.get("bg", (242, 242, 240)), float)
            is_bg = (np.abs(f - bg).max(2) <= 4).mean(1) > 0.985
        else:
            is_bg = np.zeros(len(g), bool)
        # 가장자리 검은 띠: 창이 원본 밖을 잡으면 왼·오른쪽에 검은 세로 띠가 생긴다(10-14 03편 팬)
        for side_name, cols in (("왼", slice(0, 6)), ("오른", slice(1074, 1080))):
            dark = (f[:, cols].max(2) < 40).mean(1)
            if (dark > 0.8).mean() > 0.3:
                hits.append((t, f"{side_name}쪽 검은 띠", 0, 9.9))
        ok_rows = np.ones(len(g), bool)
        ok_rows[cap0:cap1] = False                       # 자막 띠 줄은 보지 않는다
        if not flat_bg or not is_bg.any():
            continue                                     # 꽉 채운 그림·흐린 배경 팬은 위·아래 «잘림»이 아니라 화면 틀(경계를 잴 배경이 없음)
        edges = []
        def busy(y):
            # 줄의 주된 색과 14 이상 다른 픽셀 비율 — 여백 줄 ≈ 0~0.07, 사진·카드·글자를 가르면 0.1↑ (10-14 실측)
            row = f[y]
            return float((np.abs(row - np.median(row, 0)).max(1) > 14).mean())
        for y in range(len(g)):
            if not ok_rows[y] or is_bg[y]:
                continue
            above = y == 0 or (ok_rows[y - 1] and is_bg[y - 1])
            below = y == len(g) - 1 or (ok_rows[y + 1] and is_bg[y + 1])
            if above:
                rr = range(y, min(y + 3, len(g)))
                edges.append(("위", y, max(det[r] for r in rr), max(busy(r) for r in rr)))
            if below:
                rr = range(max(y - 2, 0), y + 1)
                edges.append(("아래", y, max(det[r] for r in rr), max(busy(r) for r in rr)))
        for side, y, d, bz in edges:
            # 붙인 자료의 경계 = 줄 대부분(60%↑)이 배경색이 아님. 배경 위에 떠 있는 칩·글자 한 줄은 경계가 아니다
            #   (10-14 01편: 모션그래픽 배경 = 우리 배경이라 떠 있는 요소마다 잡혀 97건 거짓 경보)
            if flat_bg and (np.abs(f[y] - bg).max(1) > 4).mean() < 0.6:
                continue
            if d > 2.5 or bz > 0.10:
                hits.append((t, side, y + TOP, max(d / 2.5, bz / 0.10)))
    # 이어지는 시각은 하나로
    merged = []
    for t, side, y, d in hits:
        for m in merged:
            if m[1] == side and t - m[2] <= step + 1e-6 and abs(m[3] - y) < 60:
                m[2], m[4] = t, max(m[4], d)
                break
        else:
            merged.append([t, side, t, y, d])
    for t0, side, t1, y, d in merged:
        if "검은 띠" in side:
            add("ERROR" if t1 - t0 >= 0.25 else "WARN", f"{t0:.2f}~{t1:.2f}s 화면", f"{side} — 창이 원본 밖을 잡음")
            continue
        # 0.5초↑ 이어지면 ERROR. 한 순간(0.25초)은 원본 장면 전환 중일 때가 많다(04편 52.8 원본 슬라이드 전환) → WARN
        lv = "ERROR" if t1 - t0 >= 0.25 else "WARN"
        add(lv, f"{t0:.2f}~{t1:.2f}s 화면", f"자료 {side} 끝(y={y})이 글자·카드·사진을 가름(기준의 {d:.1f}배)"
            + (" — 여백 줄에서 자르거나 확대를 줄일 것" if lv == "ERROR" else " — 한 순간(전환 중인지 눈으로 확인)"))


BIZ = re.compile(r"(캐피[탈달]|은행|보험|증권|주식회사|㈜|\(주\)|한의원|피부과|치과|성형외과|의원|병원|필라테스|학원|부동산|법무법인|세무)")
PHONE = re.compile(r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}")


def exposed_spans(tt):
    """글자열(공백 없음)에서 실제 업체명·전화번호로 보이는 [시작, 끝) 글자 범위들.
    업체명 = 꼬리말(캐피탈·한의원…) 앞이 한글 이름 2자 이상(○○ 은 OCR 이 O·0·C·' 로 읽는다 → 그건 가린 것)."""
    out = []
    for m in BIZ.finditer(tt):
        a = m.start()
        while a > 0 and "가" <= tt[a - 1] <= "힣":
            a -= 1
        if m.start() - a >= 2:
            out.append((a, m.end()))
    for m in PHONE.finditer(tt):
        a_, b_ = m.span()
        if (a_ == 0 or not tt[a_ - 1].isdigit()) and (b_ == len(tt) or not tt[b_].isdigit()) and "0000" not in m.group():
            out.append((a_, b_))
    return out


def check_render_log(mp4, tl, add):
    """M — 렌더러가 스스로 남긴 문제(빈 곳에 그린 표시 등)를 ERROR 로."""
    lg = Path(__file__).resolve().parents[1] / "_tmp" / "check" / (mp4.stem + ".render_log.json")
    if not lg.exists():
        add("WARN", "렌더 기록", "render_log 없음 — 렌더를 다시 하면 생김")
        return
    for e in json.loads(lg.read_text(encoding="utf-8")):
        if e["kind"] == "mark_text_missing":
            o = tl.to_out(e["src_t"])
            add("ERROR", f"{(o or 0):.2f}s(원본 {e['src_t']})", f"표시할 글자 «{e['text']}»를 화면에서 못 찾음 — 자리·시각 확인")
        if e["kind"] == "mark_empty":
            o = tl.to_out(e["src_t"])
            add("ERROR", f"{(o or 0):.2f}s(원본 {e['src_t']})", f"표시({e['type']})가 빈 곳에 먼저 그려짐 — 글자·값이 나온 뒤로 옮길 것")
        # 위치 잡기 정렬(10-15 «정렬좀 제발 똑바로해줘 … 위치정렬좀 제대로 맞춰줘»)
        o = tl.to_out(e["src_t"]) if "src_t" in e else None
        if e["kind"] == "locate_snap_empty":
            add("ERROR", f"{(o or 0):.2f}s(원본 {e['src_t']})", f"테두리 자리 {e['rect']} 에 글자가 없음 — 자리·시각 확인")
        if e["kind"] == "locate_snap_cut":
            add("ERROR", f"{(o or 0):.2f}s(원본 {e['src_t']})", f"테두리 자리 {e['rect']} 가 글자를 가름(찾은 경계 {e['found']}) — 대략 사각형을 글자 전체로")
        if e["kind"] == "locate_label_shifted":
            add("ERROR", f"{(o or 0):.2f}s(원본 {e['src_t']})", f"라벨 «{e['text']}» 가 화면 밖으로 밀려 정렬이 깨짐(dx {e['dx']}, dy {e['dy']}) — 짧게 하거나 자리(side) 바꾸기")
        if e["kind"] == "locate_label_orphan":
            add("ERROR", f"{(o or 0):.2f}s(원본 {e['src_t']})", f"라벨 «{e['text']}» 가 붙을 테두리가 그 순간 없음")


def check_overlap(plan, tl, mp4, add, step=0.25):
    """L — 자막 상자가 자료 글자를 덮는지: 상자 바로 위·아래·양옆 띠에 글자 획이 걸려 있으면 겹친 것.
    (10-14 04편 «레이아웃겹» — 확대한 휴대폰 아래 «웹사이트 클릭 …» 글씨가 자막 밑으로 들어감)"""
    from s6_render import caption_img
    caps = read_srt(mp4.with_suffix(".srt"))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={1 / step},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080)          # uint8 그대로(메모리) — 띠만 float 로
    sizes = {}
    hits = []
    for i in range(len(fr)):
        t = (i + 0.5) * step
        cur = [c for c in caps if c[0] + 0.15 <= t < c[1] - 0.05]
        if not cur or t >= tl.dur or tl.in_gap(t):
            continue
        sv = tl.to_src(t)
        if sv is None or shot_for(plan, sv)["kind"] not in ("graphic", "pan", "freeze"):
            continue
        a, b, txt = cur[0]
        if txt not in sizes:
            sizes[txt] = caption_img(txt).size
        w, h = sizes[txt]
        x0, y0 = (1080 - w) // 2, CAP_Y - h // 2
        x1, y1 = x0 + w, y0 + h
        g = fr[i]

        def busy(y_a, y_b, x_a, x_b):
            reg = g[max(y_a, 0):y_b, max(x_a, 0):min(x_b, 1080)].astype(float)
            if reg.size == 0:
                return 0.0
            return float((np.abs(reg - np.median(reg)) > 28).mean())
        sides = {"위": busy(y0 - 14, y0 - 3, x0 - 20, x1 + 20), "아래": busy(y1 + 3, y1 + 14, x0 - 20, x1 + 20),
                 "왼": busy(y0 + 6, y1 - 6, x0 - 60, x0 - 4), "오른": busy(y0 + 6, y1 - 6, x1 + 4, x1 + 60)}
        bad = [k for k, v in sides.items() if v > 0.06]
        if bad:
            hits.append((t, "·".join(bad), max(sides.values())))
    merged = []
    for t, sd, v in hits:
        if merged and t - merged[-1][1] <= step + 1e-6:
            merged[-1][1], merged[-1][3] = t, max(merged[-1][3], v)
        else:
            merged.append([t, t, sd, v])
    for t0, t1, sd, v in merged:
        lv = "ERROR" if t1 - t0 >= 0.25 else "WARN"
        add(lv, f"{t0:.2f}~{t1:.2f}s 화면", f"자막 상자 {sd}쪽에 자료 글자가 걸림(겹침 {v:.2f}) — 확대·배치를 바꿔 자막 띠 위로")


def check_splits(plan, add):
    """D3 — 렌더러가 긴 자막을 나눈 자리가 어색한지(명사+명사·꾸미는 말+받는 말 사이)."""
    from s6_render import split_caption, break_cost
    for c in plan["captions"]:
        parts = split_caption(dict(c))
        for p1, p2 in zip(parts, parts[1:]):
            if break_cost(p1["text"].split(" ")[-1], p2["text"].split(" ")[0]) > 0:
                add("ERROR", f"{c['from']:.2f}(원본) 자막", f"«{p1['text']} / {p2['text']}» — 어색한 자리에서 나눔(계획 자막을 나눠 적을 것)")


def check_joins(plan, add):
    """E·H(10-16 05편 «딴길로 샌거같잖아» «강조하는거아니면 노란색칠하지마»).
    E — 다음 조각으로 건너뛰는 자리의 마지막 자막이 뒤를 예고하는 어미(«~는데/~고/~서…»)로 끝나면 ERROR.
    H — 자막 강조(hl)가 한 자막 안에 두 번 이상 나오는 말이면(앞 하나만 칠해짐) ERROR."""
    import re
    dangling = re.compile(r"(는데|은데|인데|고|서|면|지만|니까|라서|해서|하고|거나|든지|는지|도록)[.,…?!]*$")
    voiced = [pc for pc in plan["pieces"] if not pc.get("mute")]
    for pc, nx in zip(voiced, voiced[1:]):
        if nx["in"] - pc["out"] < 0.5 or pc.get("join_ok"):   # 이어지는 말 · 같은 문장 안 군말만 덜어 낸 자리(계획에 이유 적음)
            continue
        cs = [c for c in plan["captions"] if pc["in"] - 0.1 <= c["from"] < pc["out"]]
        if not cs:
            continue
        last = max(cs, key=lambda c: c["from"])["text"].strip()
        if dangling.search(last):
            add("ERROR", f"{pc['out']:.2f}(원본) 이음", f"«{last}» — 뒤를 예고하는 어미에서 끊고 {nx['in']:.1f} 로 건너뜀(말이 닫힌 자리에서 끊을 것)")
    for c in plan["captions"]:
        hl = c.get("hl")
        if hl and c["text"].count(hl) > 1:
            add("ERROR", f"{c['from']:.2f}(원본) 자막", f"강조 «{hl}» 가 «{c['text']}» 안에 {c['text'].count(hl)}번 — 되풀이 말은 칠하지 않는다")


def check_sfx_feel(plan, add):
    """E4 결 — 통과한 효과음(소재/효과음 6개)과 소리 모양(높낮이·길이·터지는 세기)이 먼 파일은 WARN.
    설계자는 소리를 못 듣는다(10-15 «효과음은 왜 못들었어») → 숫자로 거르고, 어울림 판단은 사람. 계획 sfx 에 "role" 이 있으면 그 역할 기준과 잰다."""
    try:
        from sfx_feel import Feel
        fe = Feel()
    except Exception as e:      # 라이브러리 경로가 없으면 건너뜀
        add("WARN", "효과음 결", f"잴 수 없음({e})")
        return
    for fx in plan.get("sfx", []):
        d, ref = fe.dist(fx["file"], fx.get("role"))
        if fe.grade(d) == "멂":
            add("WARN", f"효과음 {fx.get('at', fx.get('at_typo'))}", f"«{Path(fx['file']).name}» 결이 통과 효과음과 멂({d:.2f} > {fe.far:.2f}, "
                f"가장 닮은 기준 {ref}) — `sfx_pick.py <역할>` 앞쪽 후보로")


def check_edit_style(plan, tl, add):
    """P·Q·T — 10-14 «3편은 모자이크 떡칠» «4편은 위아래 안개낀것같은느낌 + 중간에 키프레임만으로 영상대체하려는 이상한 행동».
    레퍼런스 30편: 실명은 가림이 아니라 다시 그린 화면, 끝 녹임(페이드) 0, 정지 화면을 줌·팬으로 움직이는 척 0."""
    # P 가림 떡칠: 같은 순간 가림 상자 3개↑ 또는 한 편 5개↑ → 실화면을 쓰지 말고 다시 그린다(CLAUDE.md 4)
    total = 0
    for sh in plan["shots"]:
        # locate 의 patch 는 글자가 있는 것(실명 → ○○)만 가림으로 센다(바탕색 덮개는 가림 아님)
        ms = sh.get("mask", []) + [p_["rect"] for p_ in sh.get("patch", []) if p_.get("text")]
        total += len(ms)
        for m in ms:
            a0, b0 = (m[4], m[5]) if len(m) > 5 else (sh["from"], sh["to"])
            at_once = sum(1 for n in ms if (n[4] if len(n) > 5 else sh["from"]) < b0 and (n[5] if len(n) > 5 else sh["to"]) > a0)
            if at_once >= 3:      # 실측: 통과 02편 최대 3(전화번호) · 반려 03편 38 → 4↑ ERROR
                add("ERROR" if at_once >= 4 else "WARN", f"원본 {a0:.2f}", f"가림 상자 {at_once}개가 한 화면에 — 모자이크 떡칠. 실화면 대신 다시 그린 화면(board)")
                break
    if total >= 5:
        add("ERROR", "가림", f"한 편 가림 상자 {total}개 — 실명 실화면을 쓰는 편집. 다시 그린 화면(board)으로")
    # Q 안개: 위·아래 녹임을 켜면 ERROR
    if FADE_OK or any(sh.get("fade") for sh in plan["shots"]):
        add("ERROR", "녹임", "자료 끝 녹임(페이드) 사용 — «안개낀것같은느낌». 자르는 자리를 바꾼다(K)")
    # T 키프레임 영상 대체: 정지 원본을 팬으로 훑기 금지 · 확대 키는 8초에 1번까지(강조 한 방)
    for sh in plan["shots"]:
        if sh["kind"] == "pan":
            moves = [1 for (ka, *ra), (kb, *rb) in zip(sh.get("keys", []), sh.get("keys", [])[1:])
                     if any(abs(x - y) > 1 for x, y in zip(ra, rb))]
            if moves:             # 통과 02편: 한 번 옮김 → WARN, 반려 03·04편: 3번 → ERROR
                add("ERROR" if len(moves) >= 2 else "WARN", f"원본 {sh['from']:.2f}", f"팬 이동 {len(moves)}번 — 정지 화면을 훑어 영상인 척. 요소별 하드컷(board)으로")
        if sh["kind"] == "locate":
            # 위치 잡기: 카메라 키마다 0.6초 이상 머문다(새 요소 인지 텀) · 첫 키(전체)는 0.5초 이상
            ks = [k[0] for k in sh["cam"]] + [sh["to"]]
            for i in range(len(ks) - 1):
                hold = ks[i + 1] - ks[i] - (0.35 if i else 0)
                if hold < (0.5 if i == 0 else 0.6):
                    add("WARN", f"원본 {ks[i]:.2f}", f"위치 잡기 카메라 머묾 {hold:.2f}초 — 보는 사람이 어디인지 알 틈이 없음")
        z = [k for k in sh.get("zoom", []) if k[1] > 1.0]
        dur = max(sh["to"] - sh["from"], 1)
        if len(z) > max(1, dur / 8):
            add("ERROR", f"원본 {sh['from']:.2f}", f"확대 키 {len(z)}번/{dur:.0f}초 — 키프레임으로 영상 대체. 강조 한 방만, 나머지는 하드컷·쌓기")


def check_pip_circle(plan, add):
    """U — pip 자르기 원이 원본 얼굴 원 안에 있어야 한다(10-15 «마스크 뒤에 삐져나온부분 없게끔») — 밖이면 뒤 화면 글자가 원 가장자리에 걸린다."""
    X, Y, R = PIP_CIRCLE
    for sh in plan["shots"]:
        if sh["kind"] != "pip":
            continue
        cx, cy, r = sh["circle"]
        if sh.get("studio"):          # 원본이 스튜디오 전체 화면(원본 원 PIP 아님) — 프레임 안에만 들면 된다
            if cy + r > 1080 or cx - r < 0 or cy - r < 0 or cx + r > 1920:
                add("ERROR", f"원본 {sh['from']:.2f}", f"얼굴 원 {sh['circle']} 이 원본 프레임 밖")
            continue
        over = ((cx - X) ** 2 + (cy - Y) ** 2) ** 0.5 + r - R
        if over > -4:
            add("ERROR", f"원본 {sh['from']:.2f}", f"얼굴 원 {sh['circle']} 이 원본 원 {list(PIP_CIRCLE)} 밖으로 {over + 4:.0f}px — 뒤 화면이 삐져나옴(안쪽 4px 여유)")
        if cy + r > 1080 or cx - r < 0:
            add("ERROR", f"원본 {sh['from']:.2f}", f"얼굴 원 {sh['circle']} 이 원본 프레임 밖")


def check_names(mp4, add, step=1.0):
    """N — 화면 글자 OCR(easyocr ko). 업체명 꼬리말·전화번호가 가려지지 않은 채(○○·OO·0000 아님) 보이면 ERROR."""
    try:
        import easyocr
    except ImportError:
        add("WARN", "업체명", "easyocr 없음 — 업체명 점검 못 함")
        return
    rd = easyocr.Reader(["ko", "en"], gpu=True, verbose=False)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf",
                          f"fps={1 / step},crop=1080:{BOT - TOP}:0:{TOP},format=rgb24", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, BOT - TOP, 1080, 3)
    seen = {}
    small = []
    for i in range(len(fr)):
        hs = []
        for box, txt, conf in rd.readtext(fr[i]):
            if conf < 0.35:
                continue
            ys = [p_[1] for p_ in box]
            if max(ys) < VP and conf > 0.3 and len(txt.strip()) >= 2:      # 자막 위 자료 글자만
                hs.append(max(ys) - min(ys))
            tt = txt.replace(" ", "")
            if exposed_spans(tt):
                seen.setdefault(tt, []).append((i + 0.5) * step)
        if hs:
            small.append(((i + 0.5) * step, float(np.percentile(hs, 80))))
    # R 글자 크기(10-14 «3편은 모자이크 떡칠» — 실화면을 작게 띄워 글자가 안 읽힘). 화면마다 «큰 글자 쪽»(글자 높이 80분위)을 잰다
    #   — 폰 사진 속 작은 UI 글씨는 읽으라고 둔 게 아니니 중앙값이 아니라 위쪽 분위. 실측(36px 미만 화면 비율):
    #   통과 01편 0%·02편 19% / 반려 03편 92%·04편 39% / 개편 v2 03편 6%·04편 10% → 25% 넘으면 ERROR
    if small:
        bad = [t for t, h in small if h < 36]
        if len(bad) / len(small) > 0.25:
            add("ERROR", f"{bad[0]:.1f}s~", f"자료 글자가 작음 — 큰 글자도 36px 미만인 화면 {len(bad)}/{len(small)}초. "
                "요소 하나를 크게 자르거나(board img·live) 다시 그린다")
        elif bad:
            add("WARN", f"{bad[0]:.1f}s~", f"작은 자료 글자 화면 {len(bad)}초")
    for tt, ts_ in seen.items():
        add("ERROR", f"{ts_[0]:.1f}s 화면", f"업체명·번호로 보이는 글자 «{tt}» ({len(ts_)}회) — mask 로 가릴 것(오인식이면 확인 후 무시)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mp4 = Path(args[1]) if len(args) > 1 else Path(plan["out"] + ".mp4")
    fps = plan.get("fps", 30)
    tl = Timeline(plan["pieces"])
    issues = []

    def add(level, where, msg):
        issues.append((level, where, msg))

    words = []
    if plan.get("words"):
        words = [w for r in json.loads(Path(plan["words"]).read_text(encoding="utf-8")) for w in r["words"]]

    # 목소리 기준 크기(원본 쓰는 구간)
    v = np.concatenate([rms_db(pcm(plan["src"], a, b - a), 1600) for a, b, o in tl.p])
    voice = float(np.median(v[v > -40]))
    speech_thr = voice - 12          # 이보다 크면 «말소리»

    # A 잇는 곳 말 끊김(원본 쪽)
    for k, (a, b, o) in enumerate(tl.p):
        # 잘라 «버리는» 쪽을 잰다: 시작은 바로 앞 60ms, 끝은 바로 뒤 60ms 가 말소리면 단어를 끊은 것
        #   (남기는 쪽을 재면 말 첫소리를 «말 중간»으로 오인 — ep02 CTA 2353.80)
        #   + 남기는 쪽도 말소리여야 «말을 가로질러 자른 것» — 한쪽만 소리면 정상(말 시작 직전·다음 말 직전)
        mute = [plan["pieces"][j].get("mute") for j in range(len(tl.p))]
        for edge, label, ss in ((a, "시작", a - 0.06), (b, "끝", b)):
            # 목소리를 뺀 조각(mute)은 그 조각 쪽 끝을 재지 않는다 — 소리가 안 나가니 말을 자를 일이 없다
            if mute[k]:
                continue
            if (k == 0 and label == "시작") or (k == len(tl.p) - 1 and label == "끝" and False):
                pass
            lvl_out = float(rms_db(pcm(plan["src"], ss, 0.06), 960).max())
            lvl_in = float(rms_db(pcm(plan["src"], a if label == "시작" else b - 0.04, 0.04), 640).max())
            lvl = min(lvl_out, lvl_in)
            ok = plan["pieces"][k].get("edge_ok", {}).get("start" if label == "시작" else "end")
            if lvl > speech_thr and ok:
                add("INFO", f"조각{k + 1} {label} {edge:.2f}s(원본)", f"말소리 위에서 자름({lvl:.0f}dB) — 계획에 사유: {ok}")
            elif lvl > speech_thr:
                add("ERROR", f"조각{k + 1} {label} {edge:.2f}s(원본)", f"자르는 점 60ms 가 말소리 크기({lvl:.0f}dB, 기준 {speech_thr:.0f}) — 말 중간 자름 의심")
            for w in words:   # 전사 단어 시각은 ±0.15초 틀린다 → 그 자리 음량도 말소리일 때만 경고
                if w["s"] + 0.04 < edge < w["e"] - 0.04 and lvl > speech_thr - 6:
                    add("WARN", f"조각{k + 1} {label} {edge:.2f}s(원본)", f"단어 «{w['w'].strip()}»({w['s']:.2f}~{w['e']:.2f}) 에 걸침")

    # B 숨 없이 붙음(출력)
    out_audio = pcm(mp4)
    r10 = rms_db(out_audio, 160)                  # 10ms
    for k in range(1, len(tl.p)):
        j = tl.p[k][2]                            # 출력에서 조각 시작
        gap_start = next((g0 for g0, g1 in tl.gaps if abs(g1 - j) < 1e-6), j)
        i0, i1 = int((gap_start - 0.6) * 100), int((j + 0.6) * 100)
        seg = r10[max(i0, 0):i1]
        quiet = seg < speech_thr - 6
        best, run = 0, 0
        for q in quiet:
            run = run + 1 if q else 0
            best = max(best, run)
        if best * 0.01 < 0.15:
            add("ERROR", f"잇는 곳 {j:.2f}s(출력)", f"앞뒤 무음 {best * 10}ms — 숨 없이 붙음(0.15초 이상 필요)")

    # C 전환 잔상(출력 영상)
    d = video_diffs(mp4)
    cut_thr = max(18.0, float(np.percentile(d, 99)) * 0.6)
    # 계획된 전환(push 등)·pip 성장 구간은 «움직이는 게 정상» → 컷·튀는 프레임 검사에서 뺀다
    planned = []
    for sh in plan["shots"]:
        if sh["kind"] in ("push",):
            a, b = tl.to_out(sh["from"]), tl.to_out(min(sh["to"], tl.p[-1][1]))
            if a is not None and b is not None:
                planned.append((a - 0.05, b + 0.05))
        if sh["kind"] == "pip" and sh.get("grow", True):
            a = tl.to_out(sh["from"])
            if a is not None:
                planned.append((a - 0.05, a + 0.4))
    src_motion = {}
    # 원본 자체가 크게 움직인 순간(원본 애니메이션·원본 전환)은 우리 잘못이 아니다 → 출력 시각으로 옮겨 제외
    for a, b, o in tl.p:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", plan["src"],
                              "-vf", f"fps={fps},scale=192:108,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True).stdout
        f = np.frombuffer(raw, np.uint8).reshape(-1, 108, 192).astype(float)[:, :96, :]   # 큰 움직임: 위 절반(자막·PIP 제외)
        fa = np.frombuffer(raw, np.uint8).reshape(-1, 108, 192).astype(float)[:, :96 if False else 97, :]
        sd = np.abs(np.diff(f, axis=0)).mean((1, 2))
        sda = np.abs(np.diff(fa, axis=0)).max((1, 2)) / 40.0            # 잔움직임 판정용: 자막 띠 위 전체에서 «어디라도» 움직였나
        for i, v in enumerate(sda):
            src_motion[int(round((o + (i + 1) / fps) * fps))] = float(v)
            if v > 3:          # 원본 연출(어두워짐·시간 흐름 등) 프레임 — 4.8~5.6 짜리도 있었다(ep02 1612.7)
                t = o + (i + 1) / fps
                planned.append((t - 0.1, t + 0.1))
    for sh in plan["shots"]:
        for z in sh.get("zoom", []):
            o = tl.to_out(z[0])
            if o is not None:
                planned.append((o - 0.05, o + 0.45))
        for m in sh.get("marks", []):
            o = tl.to_out(m["at"])
            if o is not None:
                planned.append((o - 0.05, o + 0.45))
        if sh["kind"] == "locate":                    # 위치 잡기 카메라 이동(전체 → 칸, 0.35초) — 사장님이 고른 연출(10-15 «1번이맞지»)
            for k in sh["cam"][1:]:
                o = tl.to_out(k[0])
                if o is not None:
                    planned.append((o - 0.05, o + 0.45))
        if sh["kind"] == "pan":                       # 팬 이동 구간
            for (ka, *ra), (kb, *rb) in zip(sh["keys"], sh["keys"][1:]):
                oa, ob = tl.to_out(ka), tl.to_out(kb)
                if oa is not None and ob is not None and any(abs(x - y) > 1 for x, y in zip(ra, rb)):
                    planned.append((oa - 0.05, ob + 0.05))
    in_planned = lambda t: any(x <= t <= y for x, y in planned)
    cuts = [i + 1 for i in range(len(d)) if d[i] > cut_thr and not in_planned((i + 1) / fps)]
    for c in cuts:
        after = d[c:c + int(0.5 * fps)]
        moving = int((after[3:] > cut_thr * 0.35).sum()) if len(after) > 3 else 0
        if moving >= 3:
            add("ERROR", f"{c / fps:.2f}s", f"컷 직후 0.1~0.5초에 화면이 계속 크게 바뀜({moving}프레임) — 원본 전환 효과가 따라 들어옴")
    for i in range(1, len(d)):
        if d[i - 1] > cut_thr and d[i] > cut_thr and not in_planned(i / fps):
            add("ERROR", f"{i / fps:.2f}s", "튀는 한 프레임(앞뒤와 모두 크게 다름)")

    # S 소리만 나고 화면 변화 없음(10-13 «14초에 효과음만 나오고 아무런 연출이없잖아 이런거 검사기에 넣어서»)
    #   롱폼에 구운 효과음은 원본 화면이 바뀌는 순간에 있다 → 원본(쓰는 구간)의 화면 변화 순간을 찾고,
    #   출력에서 같은 순간 ±0.2초에 내용 칸 변화가 없으면 = 그 변화가 잘려 나가 소리만 남은 것.
    #   원본 비교 영역: 구운 자막 띠(y≥960)·PIP 원(x<340, y≥740) 제외.
    sd = source_diffs(plan["src"], tl.p)
    for s_t, val in sd:
        o = tl.to_out(s_t)
        if o is None or shot_for(plan, s_t)["kind"] == "typo":    # CTA 타이포 장면은 원본 화면을 안 쓴다
            continue
        i0, i1 = max(int((o - 0.2) * fps) - 1, 0), int((o + 0.2) * fps)
        local = d[i0:i1]
        wc = window_change(o, fps, 0.15, 0.35)
        lb = np.array([wc])
        if len(local) and local.max() < max(0.5, val * 0.15) and wc < 4.0:
            add("ERROR", f"{o:.2f}s(원본 {s_t:.2f})", f"원본 화면이 바뀌는 순간(차이 {val:.1f}) — 출력은 변화 {local.max():.2f}·칸 {lb.max():.1f}뿐. "
                "구운 효과음만 남음(잘려 나갔거나 자막 띠 밑에서 바뀜)")

    # S2 자른 영역 밖에서 원본이 바뀜(카드·칩이 잘려 나가 그 효과음만 남는 경우 — 01편 «받은 설정» 카드 837.8)
    #   샷마다 쓰는 원본 영역(crop + overlays)을 빼고, 나머지(구운 자막 띠·PIP 제외)의 0.2초 간격 변화를 본다.
    for ev_t, val in outside_changes(plan, tl):
        o = tl.to_out(ev_t)
        if o is None:
            continue
        i0, i1 = max(int((o - 0.2) * fps) - 1, 0), int((o + 0.3) * fps)
        local = d[i0:i1]
        if len(local) and local.max() < 1.0:
            add("ERROR", f"{o:.2f}s(원본 {ev_t:.2f})",
                f"자른 영역 밖 원본 변화 {val:.1f}(카드·칩 등장?) — 출력 변화 {local.max():.2f}. 그 효과음만 남음 → overlays 로 들여오기")

    # H 화면 멈춤(10-13 «14초, 47초 이쪽 잠깐 애니메이션이 멈추는데 이런 멈추는 지점이 없으면»)
    #   실측(01편): 정지 화면·정지 카드 프레임 차이 중앙 0.006~0.03 / 원본 모션그래픽의 «쉼» 0.1~0.3 → 기준 0.05
    #   10-14: 평균만 보면 밑줄·상자 같은 작은 연출도 «멈춤»으로 센다 → 칸(12×9) 최댓값 2 이상이면 변화로 본다
    #   0.3초에 걸쳐 그려지는 밑줄은 프레임끼리 차이가 작다 → 6프레임(0.2초) 떨어진 프레임끼리 칸 최댓값도 본다
    F = FRAMES_K
    hh_, ww_ = F.shape[1] // 12 * 12, F.shape[2] // 9 * 9
    lag = np.zeros(len(d))
    for i in range(6, len(d)):
        df = np.abs(F[i + 1, :hh_, :ww_] - F[i - 5, :hh_, :ww_])
        lag[i] = df.reshape(12, hh_ // 12, 9, ww_ // 9).mean((1, 3)).max()
    still = (d < 0.05) & (BLOCK_D[:len(d)] < 2.0) & (lag < 3.0)
    run = 0
    for i, st in enumerate(list(still) + [False]):
        if st:
            run += 1
        else:
            if run >= int(1.0 * fps):
                t0 = (i - run) / fps
                # 10-13 사장님: 짧은 정지는 괜찮다, 길면 도구 연출·키프레임 확대로 끊는다 → 2초 이상 ERROR
                add("ERROR" if run >= int(2.0 * fps) else "WARN", f"{t0:.2f}s",
                    f"화면 멈춤 {run / fps:.2f}초 — 새 정보(쌓기·하드컷·얼굴)로 끊기(줌·팬으로 때우지 않는다 — T)")
            run = 0

    # J 잔움직임(10-13 «카메라구도가 너무 움직이고 잔흔들림이 너무심해»): 원본은 멈췄는데 출력만 미세하게 계속 움직임
    #   (정수 픽셀 줌·숨쉬기 등). 계획된 움직임(줌 키 0.4초·도구 연출 0.4초·오버레이 등장·전환)은 뺀다.
    intended = list(planned)
    for sh in plan["shots"]:
        for z in sh.get("zoom", []):
            o = tl.to_out(z[0])
            if o is not None:
                intended.append((o - 0.05, o + 0.45))
        for m in sh.get("marks", []):
            o = tl.to_out(m["at"])
            if o is not None:
                intended.append((o - 0.05, o + 0.45))
        for ov in sh.get("overlays", []):
            if ov.get("from") is not None:
                o = tl.to_out(ov["from"])
                if o is not None:
                    intended.append((o - 0.05, o + 0.3))
        if sh["kind"] in ("typo", "pan", "pip", "card"):
            a0 = tl.to_out(max(sh["from"], tl.p[0][0]))
            if sh["kind"] == "typo":
                intended.append((a0 - 1 if a0 else tl.dur - 10, 1e9))
            elif sh["kind"] == "pan":
                for (ka, *ra), (kb, *rb) in zip(sh["keys"], sh["keys"][1:]):
                    oa, ob = tl.to_out(ka), tl.to_out(kb)
                    if oa is not None and ob is not None and any(abs(x - y) > 1 for x, y in zip(ra, rb)):
                        intended.append((oa, ob + 0.05))
            elif sh["kind"] in ("pip", "card"):
                if a0 is not None:
                    intended.append((a0 - 0.05, a0 + 0.4))
    run = 0
    for i in range(len(d)):
        t = (i + 1) / fps
        jit = 0.06 < d[i] < 1.5 and src_motion.get(i + 1, 0) < 0.05 and not any(x <= t <= y for x, y in intended)
        if jit:
            run += 1
        else:
            if run >= int(0.5 * fps):
                add("ERROR", f"{(i - run) / fps:.2f}s", f"잔움직임 {run / fps:.2f}초 — 원본은 멈췄는데 화면만 미세하게 흔들림")
            run = 0

    # D 자막
    caps = sorted(plan["captions"], key=lambda c: c["from"])
    for c in caps:
        a, b = tl.to_out(c["from"]), tl.to_out(c["to"])
        if a is None or b is None:
            continue
        if b - a < 0.6:
            add("WARN", f"{a:.2f}s 자막", f"«{c['text']}» {b - a:.2f}초 — 인지 텀 0.6초 미만")
        if len(c["text"].replace(" ", "")) > 15:
            add("INFO", f"{a:.2f}s 자막", f"«{c['text']}» 15자 초과 → 렌더러가 둘로 나눔")
    for c1, c2 in zip(caps, caps[1:]):
        a, b = tl.to_out(c1["to"]), tl.to_out(c2["from"])
        if a is not None and b is not None and b - a > 0.4:
            add("WARN", f"{a:.2f}s 자막", f"자막 빈칸 {b - a:.2f}초")

    # E 효과음
    fx = []
    for f in plan.get("sfx", []):
        if "at_typo" in f:
            ty = [sh for sh in plan["shots"] if sh["kind"] == "typo"]
            outs = [tl.to_out(max(a, ty[0]["from"])) for a, b, o in tl.p if ty and b > ty[0]["from"] and a < ty[0]["to"]]
            outs = [x for x in outs if x is not None]
            st0 = min(outs) if outs else tl.dur
            st0 -= next((g1 - g0 for g0, g1 in tl.gaps if abs(g1 - st0) < 1e-6), 0)
            at = st0 + f["at_typo"]
        else:
            at = tl.to_out(f["at"]) if f["at"] != "end" else tl.dur
        if at is None:
            add("ERROR", f"효과음 {f['at']}", "쓰지 않는 원본 구간에 걸림")
            continue
        fx.append((at, Path(f["file"]).name, f))
        if "rel" not in f:
            add("WARN", f"{at:.2f}s 효과음", f"{Path(f['file']).name} — rel(목소리 대비) 미지정")
    fx.sort()
    # E2 우리 효과음마다 화면 변화 짝(±0.1~0.35초, 자막 띠 제외 칸 최댓값 3↑) — 소리만 나는 효과음 금지
    for at, n, f in fx:
        wc = window_change(at, fps)
        if wc < 4.0:
            add("ERROR", f"{at:.2f}s 효과음", f"{n}({f.get('_역할', '')}) — 화면 변화 없음(앞뒤 비교 {wc:.1f}). 소리만 남")
    for (a1, n1, _), (a2, n2, _) in zip(fx, fx[1:]):
        if a2 - a1 < 0.12:
            add("ERROR", f"{a1:.2f}s 효과음", f"{n1}·{n2} 0.12초 안에 겹침")
        if n1 == n2 and a2 - a1 < 3:
            add("ERROR", f"{a1:.2f}s 효과음", f"{n1} 3초 안 반복")
    # E3 한 편 안 같은 파일 반복(10-14 «효과음 그냥 너무 반복되는데?»): 3회↑ ERROR · 연달아(사이에 다른 소리 없이) 같은 파일 WARN
    cnt = {}
    for at, n, f in fx:
        cnt.setdefault(n, []).append(at)
    for n, ats in cnt.items():
        if len(ats) >= 3:
            add("ERROR", f"{ats[0]:.2f}s 효과음", f"{n} 한 편에 {len(ats)}회({', '.join(f'{a:.1f}' for a in ats)}) — 2회까지. "
                "`tools/sfx_pick.py <역할> --plan` 으로 다른 후보")
    for (a1, n1, _), (a2, n2, _) in zip(fx, fx[1:]):
        if n1 == n2 and a2 - a1 >= 3:
            add("WARN", f"{a1:.2f}s 효과음", f"{n1} 연달아 두 번({a1:.1f}·{a2:.1f}) — 다른 후보로 바꾸면 덜 반복됨")
    for i in range(len(fx)):
        chain = [x for x in fx if fx[i][0] <= x[0] < fx[i][0] + 3]
        if len(chain) > 3:
            add("WARN", f"{fx[i][0]:.2f}s 효과음", f"3초 안 {len(chain)}개")

    # L 길이(10-16 «쇼츠 너무 길어 항상 쇼츠는 40~60초 사이로 해주고») — 엔딩 포함 완성본 길이
    dur_out = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)],
                                   capture_output=True, text=True).stdout.strip() or 0)
    if not 40.0 <= dur_out <= 60.0:
        add("ERROR", "길이", f"완성본 {dur_out:.1f}초 — 쇼츠는 40~60초. 되풀이·군말·덧붙임 말을 덜어 맞춘다")

    # F 끝
    if plan.get("ending"):
        add("ERROR", "끝", "엔딩 카드가 있음 — 10-13 «마지막에 얼굴나오는건 하지마»")
    last = max(j for j in range(len(tl.p)) if not plan["pieces"][j].get("mute"))   # 소리 나는 마지막 조각
    a, b, o = tl.p[last]
    lvl = float(rms_db(pcm(plan["src"], b - 0.05, 0.05), 800).max())
    if lvl > speech_thr:
        add("ERROR", f"끝 {b:.2f}s(원본)", f"마지막 50ms 가 말소리({lvl:.0f}dB) — 말끝이 잘림")

    # G 음량
    er = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"],
                        capture_output=True, text=True, errors="replace").stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", er)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", er)[-1])
    if abs(I + 14) > 1:
        add("WARN", "음량", f"통합 {I} LUFS(−14±1)")
    if tp > -1.0:
        add("WARN", "음량", f"트루피크 {tp} dBFS(≤ −1.0)")

    # D2 자막 싱크 · K 자료 잘림 · N 업체명 (완성본 기준)
    check_sync(mp4, add)
    check_cut(plan, tl, mp4, add)
    check_render_log(mp4, tl, add)
    check_overlap(plan, tl, mp4, add)
    check_splits(plan, add)
    check_joins(plan, add)
    check_edit_style(plan, tl, add)
    check_pip_circle(plan, add)
    check_sfx_feel(plan, add)
    if "--no-ocr" not in sys.argv:
        check_names(mp4, add)

    # 보고
    print(f"점검: {mp4.name} · 목소리 {voice:.0f}dB · 컷 {len(cuts)}곳 · 효과음 {len(fx)}개 · {I} LUFS / TP {tp}")
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for lv, wh, msg in sorted(issues, key=lambda x: order[x[0]]):
        print(f"  [{lv}] {wh}: {msg}")
    n_err = sum(1 for x in issues if x[0] == "ERROR")
    print(f"ERROR {n_err} · WARN {sum(1 for x in issues if x[0] == 'WARN')}")
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
