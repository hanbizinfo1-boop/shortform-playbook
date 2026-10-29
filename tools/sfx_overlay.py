# -*- coding: utf-8 -*-
"""완성 영상(자막까지 끝난 것)에 효과음·장면음·BGM 을 얹는다 — 영상은 그대로 복사, 오디오만 새로 섞음.

    python tools/sfx_overlay.py <큐.json>

큐.json:
  "src": 원본 mp4, "out": 출력 mp4
  "sfx": [{"at": 초, "file": 경로, "rel": 목소리 대비 dB, "align": "peak"(휙 — 정점을 at 에) | 생략(들리는 시작을 at 에),
           "max": 최대 길이 초(기본 2.5), "pre": 휙 정점 앞 최대 초(기본 0.25), "series": 묶음 이름(같은 그림이 이어지는 열거 — 평면도 74·84·114 — 는 같은 소리로 통일, 반복 경고 제외), "_뜻": 메모}]
  "beds": [{"from": 초, "to": 초, "file": 경로, "rel": 목소리 대비 dB(RMS 평균), "off": 파일 안 시작 초(생략 = 가장 큰 곳 중심),
            "_뜻": 메모}]   — 장면음: 그 동작이 화면에 보이는 동안 내내(열차 운행·차 지나감·드론). 짧은 파일은 이어 붙여 늘림
  "bgm": {"file": 경로, "rel": 목소리 대비 dB(기본 −13), "end_at": 곡 끝을 맞출 영상 시각(기본 영상 끝), "fade_in": 초, "gap_db": 말 쉼에서 올릴 dB(기본 6)}

근거(sfx.md 2·3장 · 영상제작 효과음-브랜드홍보-원칙 0·5·6장 · 효과음.md 09-28 BGM 체인):
- 들리는 시각으로 맞춤(때림 = 5ms RMS 정점 −6dB 첫 도달을 at 에, 그 앞 30ms 만 · 휙은 정점을 at 에, 앞 부풂 0.25초까지) · 자연 길이 최대 2.5초 + 끝 페이드 · 효과음끼리 겹치면 앞 소리를 다음 어택 10ms 전에 끊음
- 다듬기: 고역(2kHz↑) 40% 넘는 소리는 5kHz 셸빙 −6dB · 10ms 안 +18dB 넘게 솟는 소리는 앞 30ms 페이드인
- 효과음 버스에 짧은 울림(43·71·113ms) — 따로 놀지 않게
- BGM: 곡의 자연스러운 끝을 영상 끝에 · 50Hz 아래 정리 · 2.5kHz −4dB(목소리 대역 비켜 주기) · 9kHz 셸빙 −2.5dB ·
  목소리 대비 −13dB 바탕 + 말 쉼(0.35초↑)에서 6dB 올라옴 · 큰 효과음 순간 −3dB
- 크기는 가장 큰 0.1초 RMS 를 목소리 대비 rel · 마감 −14 LUFS · 트루피크 −1.5dB 이하
10-19 ○○역 분양 쇼츠 2편(«효과음처리 한번 영상에 맞게 잘넣어봐» → «지하철이 운행하면 그만큼 지하철소리도 길게 … bgm까지 넣어서 완성»).
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000


def decode(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{ss:.3f}", "-t", f"{t:.3f}"] if ss is not None else []) + \
          ["-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).reshape(-1, 2).copy()


def rms_db(x, win):
    m = x.mean(1)
    n = int(SR * win)
    r = [np.sqrt((m[i:i + n] ** 2).mean()) for i in range(0, max(len(m) - n, 1), max(n // 2, 1))]
    return 20 * np.log10(np.array(r) + 1e-9)


def onset_and_peak(x):
    """파일 시작 → 들리는 시작(20ms RMS 가 정점 −20dB 첫 도달), 정점(20ms RMS 최대)까지 초."""
    m = x.mean(1)
    n = int(SR * 0.02)
    r = np.array([np.sqrt((m[i:i + n] ** 2).mean()) for i in range(0, max(len(m) - n, 1), n)])
    db = 20 * np.log10(r + 1e-9)
    pk = int(np.argmax(db))
    on = int(np.argmax(db >= db[pk] - 20))
    return on * n / SR, pk * n / SR


def attack(x):
    """파일 시작 → 들리는 때림(5ms RMS 가 정점 −6dB 첫 도달)까지 초."""
    m = x.mean(1)
    n = int(SR * 0.005)
    r = np.array([np.sqrt((m[i:i + n] ** 2).mean()) for i in range(0, max(len(m) - n, 1), n)])
    db = 20 * np.log10(r + 1e-9)
    return int(np.argmax(db >= db.max() - 6)) * n / SR


def natural_len(x, lim):
    """잦아드는 데까지(정점 −40dB 아래로 0.1초 머무는 첫 자리), 최대 lim 초."""
    db = rms_db(x, 0.05)                       # 0.025초 간격
    pk = db.max()
    quiet = db < pk - 40
    for i in range(int(np.argmax(db)), len(db) - 4):
        if quiet[i:i + 4].all():
            return min(lim, i * 0.025 + 0.05)
    return min(lim, len(x) / SR)


def shelf(x, f0, gain_db):
    """고역 셸빙 근사: 고역 성분(f0 위)을 gain 만큼."""
    hi = sosfilt(butter(2, f0, "highpass", fs=SR, output="sos"), x, axis=0)
    return x + hi * (10 ** (gain_db / 20) - 1)


def tidy(x):
    """효과음 다듬기(효과음-브랜드홍보-원칙 6장): 고역 셈 → 셸빙 −6dB, 날카로운 순간음 → 앞 30ms 페이드인."""
    m = x.mean(1)
    spec = np.abs(np.fft.rfft(m)) ** 2
    fr = np.fft.rfftfreq(len(m), 1 / SR)
    if spec[fr >= 2000].sum() / (spec.sum() + 1e-12) > 0.40:
        x = shelf(x, 5000, -6)
    db = rms_db(x[:int(0.1 * SR)], 0.005) if len(x) > int(0.02 * SR) else np.array([0.0])
    if len(db) > 4 and db[:4].max() - db[0] > 18:
        f = int(0.03 * SR)
        x = x.copy()
        x[:f] *= np.linspace(0, 1, f)[:, None]
    return x


def loop_to(x, n, xf=0.12):
    """짧은 장면음을 이어 붙여 n 샘플로(이음새 0.12초 크로스페이드)."""
    if len(x) >= n:
        return x[:n]
    k = int(xf * SR)
    out = x.copy()
    while len(out) < n:
        a, b = out[-k:], x[:k]
        r = np.linspace(0, 1, k)[:, None]
        out = np.concatenate([out[:-k], a * (1 - r) + b * r, x[k:]])
    return out[:n]


def fade(x, fin, fout):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, min(a, len(x)))[:, None]
    if b:
        x[len(x) - b:] *= np.linspace(1, 0, min(b, len(x)))[:, None]
    return x


def synth_rumble(n, seed=7):
    """솟아오르는 땅울림(트레일러 문법: 저역 럼블이 필터·음높이를 올리며 부풀다 타격에서 정점).
    갈색 잡음 → 시간에 따라 열리는 저역 필터(150 → 700Hz) + 사인 스윕 38 → 75Hz, 세기는 끝으로 갈수록 부풂."""
    rng = np.random.default_rng(seed)
    w = np.cumsum(rng.standard_normal(n)) * 0.02
    w -= np.convolve(w, np.ones(4801) / 4801, mode="same")      # 아주 느린 흐름 제거
    out = np.zeros(n)
    blk = int(0.05 * SR)
    zi = None
    for i in range(0, n, blk):
        p = i / max(n - 1, 1)
        sos = butter(2, 150 + 550 * p ** 1.5, "lowpass", fs=SR, output="sos")
        if zi is None:
            from scipy.signal import sosfilt_zi
            zi = sosfilt_zi(sos) * w[0]
        seg, zi = sosfilt(sos, w[i:i + blk], zi=zi)
        out[i:i + blk] = seg
    t = np.arange(n) / SR
    f = 38 + 37 * (t / t[-1]) ** 1.5
    sine = np.sin(2 * np.pi * np.cumsum(f) / SR)
    out = out / (np.abs(out).max() + 1e-9) + 0.6 * sine
    env = (np.linspace(0, 1, n) ** 2.2) * 0.9 + 0.1
    out *= env
    return np.stack([out, out], 1).astype(np.float32)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cue = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    src, out = Path(cue["src"]), Path(cue["out"])
    voice = decode(src)
    N = len(voice)
    vdb = rms_db(voice, 0.1)
    voice_db = float(np.median(vdb[vdb > -40]))               # 말하는 칸 0.1초 RMS 중앙값
    report = []

    # ---------- 효과음(타격) ----------
    items = []
    for fx in sorted(cue.get("sfx", []), key=lambda f: f["at"]):
        x = tidy(decode(fx["file"]))                       # 다듬은 뒤에 때림을 잼(고역 셸빙이 때림 자리를 옮김)
        on, pk = onset_and_peak(x)
        if fx.get("align") == "peak":
            # 정점 앞 부풂은 최대 pre 초(기본 0.25)만 — 길게 부푸는 휙이 앞 효과음을 덮고 그림보다 앞서 들리지 않게
            cut = max(on, pk - fx.get("pre", 0.25))
            x = x[int(cut * SR):].copy()
            lead = pk - cut
            f = int(min(0.08, lead) * SR)
            if cut > on and f:
                x[:f] *= np.linspace(0, 1, f)[:, None]
        else:
            # 들리는 «때림»(5ms RMS 가 정점 −6dB 첫 도달)을 at 에 — −20dB 시작에 맞추면 천천히 부푸는 소리
            # (sfx-impact 0.78초·종이소리 0.62초)가 그림보다 늦게 들림(10-19 «효과음 싱크가 너무안맞음»).
            # 그 앞은 최대 30ms 만 남기고 페이드인
            hit = attack(x)
            cut = max(on, hit - 0.03)
            x = x[int(cut * SR):].copy()
            lead = hit - cut
            f = int(lead * SR)
            if f:
                x[:f] *= np.linspace(0, 1, f)[:, None]
        x = x[:int(natural_len(x, fx.get("max", 2.5)) * SR)]
        g = 10 ** ((voice_db + fx["rel"] - rms_db(x, 0.1).max()) / 20)
        items.append({"st": fx["at"] - lead, "x": x * g, "fx": fx})
    for i, it in enumerate(items):
        # 겹침: 앞 소리를 다음 소리 시작 10ms 전까지 — 끝은 남은 길이의 25%(0.08~0.3초)로 잦아들게(뚝 끊김 금지,
        # 10-19 «교통도 잡았어 할때 효과음 끊기는거 … 몰입감해침»). 자연 길이의 60% 못 남으면 WARN — 큐를 솎아서 고친다
        x = it["x"]
        nat = len(x) / SR
        if i + 1 < len(items):
            cut = items[i + 1]["st"] - 0.010 - it["st"]
            if cut < nat:
                x = x[:max(int(cut * SR), 1)]
                if nat > 0.5 and cut < 0.6 * nat:
                    report.append(f"[WARN] {it['fx']['at']:.2f} {Path(it['fx']['file']).name} 자연 {nat:.2f}초 → "
                                  f"{cut:.2f}초에서 잘림")
        kept = len(x) / SR
        it["x"] = fade(x, 0, max(min(0.08, kept), min(0.3, kept * 0.25)))
    # 싱크 점검: 놓인 소리의 때림(휙은 정점)이 at 에서 2프레임(30fps) 넘게 벗어나면 WARN
    for it in items:
        x = it["x"]
        if len(x) < int(0.02 * SR):
            continue
        hit = onset_and_peak(x)[1] if it["fx"].get("align") == "peak" else attack(x)
        off = it["st"] + hit - it["fx"]["at"]
        if abs(off) > 0.067:
            report.append(f"[WARN] 싱크 {it['fx']['at']:.2f} {Path(it['fx']['file']).name} 때림 {off:+.3f}초")
    bus = np.zeros_like(voice)
    for it in items:
        s = int(max(it["st"], 0) * SR)
        x = it["x"][int(max(-it["st"], 0) * SR):]
        e = min(N, s + len(x))
        bus[s:e] += x[:e - s]

    # ---------- 장면음(동작이 보이는 동안 내내) ----------
    beds = np.zeros_like(voice)
    for bd in cue.get("beds", []):
        n = int((bd["to"] - bd["from"]) * SR)
        x = synth_rumble(n) if bd["file"] == "synth:rumble" else decode(bd["file"])
        if bd["file"] == "synth:rumble":
            pass
        elif "off" in bd:
            x = x[int(bd["off"] * SR):]
        elif len(x) > n:                                       # 가장 큰 곳을 가운데 두고 자름
            _, pk = onset_and_peak(x)
            s = int(min(max(pk * SR - n / 2, 0), len(x) - n))
            x = x[s:]
        x = loop_to(x, n)
        x = fade(x, min(0.15, bd.get("fade_in", 0.15)), min(bd.get("fade_out", 0.3), n / SR / 3))
        lv = rms_db(x, 0.1)
        g = 10 ** ((voice_db + bd["rel"] - float(np.mean(lv[lv > lv.max() - 30]))) / 20)
        s = int(bd["from"] * SR)
        e = min(N, s + n)
        beds[s:e] += x[:e - s] * g

    # 효과음 버스 짧은 울림(43·71·113ms) — 따로 놀지 않게
    wet = bus + beds
    rev = np.zeros_like(wet)
    for ms, dbv in ((43, -14), (71, -17), (113, -20)):
        d = int(ms * SR / 1000)
        rev[d:] += wet[:-d] * 10 ** (dbv / 20)
    fxsum = wet + rev

    # ---------- BGM ----------
    music = np.zeros_like(voice)
    if cue.get("bgm"):
        bg = cue["bgm"]
        y = decode(bg["file"])
        ydb = rms_db(y, 0.1)                                   # 곡의 자연스러운 끝 = 정점 −40dB 위 마지막 칸
        end = (np.nonzero(ydb > ydb.max() - 40)[0][-1] + 2) * 0.05
        end_at = bg.get("end_at", N / SR)
        s_song = end - end_at                                  # 영상 0초에 해당하는 곡 시각
        y = y[max(int(s_song * SR), 0):]
        if s_song < 0:
            y = np.concatenate([np.zeros((int(-s_song * SR), 2), np.float32), y])
        y = np.pad(y, ((0, max(0, N - len(y))), (0, 0)))[:N]
        y = sosfilt(butter(2, 50, "highpass", fs=SR, output="sos"), y, axis=0)
        bp = sosfilt(butter(2, [1800, 3400], "bandpass", fs=SR, output="sos"), y, axis=0)
        y = y + bp * (10 ** (-4 / 20) - 1)                     # 2.5kHz 부근 −4dB
        y = shelf(y, 9000, -2.5)
        y = fade(y, bg.get("fade_in", 0.3), 0.4)
        lv = rms_db(y, 0.1)
        base = 10 ** ((voice_db + bg.get("rel", -13) - float(np.mean(lv[lv > lv.max() - 25]))) / 20)
        # 말 쉼(0.35초↑)에서 6dB 올라오고, 큰 효과음(목소리 대비 0dB↑) 순간 −3dB
        env_t = np.arange(0, N / SR, 0.01)
        vv = np.interp(env_t, np.arange(len(vdb)) * 0.05 + 0.05, vdb)
        speak = vv > voice_db - 15
        gain = np.where(speak, 0.0, bg.get("gap_db", 6.0))       # 말 쉼에서 올림(레퍼런스 분양 쇼츠는 약 2dB)
        k = 35                                                 # 0.35초 안 숨은 메움
        run = 0
        for i in range(len(gain)):
            run = run + 1 if not speak[i] else 0
            if 0 < run < k:
                gain[i] = 0.0
        for it in items:
            if it["fx"]["rel"] >= 0:
                a = int(it["fx"]["at"] / 0.01)
                gain[a:a + 40] = np.minimum(gain[a:a + 40], -3.0)
        for a, z, dbv in bg.get("dips", []):                   # 큰 공개 앞 음악 빼기(라이저 → 타격에서 복귀)
            gain[int(a / 0.01):int(z / 0.01)] = np.minimum(gain[int(a / 0.01):int(z / 0.01)], dbv)
        sm = np.convolve(gain, np.ones(15) / 15, mode="same")  # 0.15초 부드럽게
        env = np.interp(np.arange(N) / SR, env_t, 10 ** (sm / 20))
        music = y * base * env[:, None]

    mix = voice + fxsum + music
    # 크기 점검(10-19): 목소리 대비 BGM·효과음 크기를 섞기 전 신호로 바로 잼 — 완성본에서 목소리를 빼서 재면
    # AAC·리미터 오차(약 −14dB)에 묻혀 BGM 이 실제보다 크게 나옴(«제리의 역습 소리가 하나도안들려»)
    def _lv(x):
        r = rms_db(x, 0.1)
        return r
    vdb2, mdb, fdb = _lv(voice), _lv(music), _lv(bus)
    sp = vdb2 > voice_db - 12
    if sp.any() and music.any():
        print(f"점검 BGM−목소리: 말할 때 {np.median(mdb[sp]) - voice_db:+.1f}dB · 쉼 {np.median(mdb[~sp]) - voice_db:+.1f}dB")
    hits = fdb[fdb > voice_db - 40]
    if hits.size:
        print(f"점검 효과음(0.1초 RMS, 들리는 칸) 중앙 {np.median(hits) - voice_db:+.1f}dB · 상위10% {np.percentile(hits, 90) - voice_db:+.1f}dB")
    if cue.get("stems_dir"):
        import soundfile as sf
        sd = Path(cue["stems_dir"])
        sd.mkdir(parents=True, exist_ok=True)
        for nm, x in (("voice", voice), ("fx", bus), ("beds", beds), ("music", music)):
            sf.write(sd / f"{nm}.wav", x, SR, subtype="FLOAT")
    # 반복 점검(sfx.md 2장): 한 편 같은 파일 2회까지 · 같은 파일 3초 안 연달아 금지
    names = Counter(Path(f["file"]).name for f in cue.get("sfx", []) if "series" not in f)
    report += [f"[WARN] 같은 파일 {n}회: {k}" for k, n in names.items() if n > 2]
    last = {}
    for it in items:
        k = Path(it["fx"]["file"]).name
        if "series" in it["fx"]:
            continue
        if k in last and it["fx"]["at"] - last[k] < 3:
            report.append(f"[WARN] {k} 3초 안 반복 ({last[k]:.2f} → {it['fx']['at']:.2f})")
        last[k] = it["fx"]["at"]

    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".mix.wav")
    import soundfile as sf
    sf.write(wav, mix, SR, subtype="FLOAT")
    er = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "ebur128", "-f", "null", "-"],
                        capture_output=True, text=True, errors="replace").stderr
    adj = -14.0 - float(re.findall(r"I:\s+(-?[\d.]+) LUFS", er)[-1])
    lim = 0.75
    for _ in range(5):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", f"volume={adj:.2f}dB,alimiter=limit={lim:.3f}:level=false",
                        "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)],
                       check=True)
        er2 = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"],
                             capture_output=True, text=True, errors="replace").stderr
        tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", er2)[-1])
        lu = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", er2)[-1])
        if tp <= -1.5:
            break
        lim *= 0.89
    wav.unlink()
    print(f"완성 {out} · 효과음 {len(items)}개 · 장면음 {len(cue.get('beds', []))}개 · BGM "
          f"{Path(cue['bgm']['file']).name if cue.get('bgm') else '없음'} · 목소리 {voice_db:.1f}dB · {lu:.1f} LUFS · TP {tp:.1f}")
    for r in report:
        print(r)


if __name__ == "__main__":
    main()
