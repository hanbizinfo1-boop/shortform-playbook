# -*- coding: utf-8 -*-
"""효과음 «결» 재기 — 귀 대신 숫자로. 통과한 효과음(기준)과 소리 모양이 얼마나 닮았는지 잰다.

근거: 사장님 10-15 «효과음은 왜 못들었어» → «넣어». 설계자는 소리를 듣지 못한다 → 사장님이 통과시킨 소리를 기준으로
      높낮이 분포·길이·터지는 세기가 비슷한 파일만 후보로 올린다. (어울림의 최종 판단은 여전히 사람 — 이건 거르는 체)

    python tools/sfx_feel.py <파일 또는 계획.json> ...      # 기준과의 거리 · 가까움/보통/멂
    (sfx_pick.py 가 후보 정렬에, s6_check 가 E4 경고에 쓴다)

기준(REFS) = 빡이사DB 01·02편(업로드 끝 = 통과)과 그 전 통과 편에 쓴 이 저장소 소재/효과음 6개.
역할마다 가장 가까운 기준(ROLE_REF)이 있으면 그것과, 없으면 기준 전체 중 가장 가까운 것과 잰다.
특징(소리 앞뒤 무음 −50dB 잘라 냄):
  dur 길이 · attack 터지기까지 · decay 피크→−20dB · centroid 소리 중심 높이 · rolloff 85% 높이 ·
  low/mid/high/air 대역 비율(<250 · 250~2k · 2k~6k · >6k Hz) · flat 잡음성(1=쉬익, 0=음정) · crest 튀는 정도
값은 라이브러리 전체 기준으로 표준화(로그 축은 길이·높이). 캐시 `_tmp/sfx_feat.json`(다시 만들 수 있음).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "소재" / "효과음"
LIB = Path("D:/영상제작/소재/예능효과음")
CACHE = ROOT / "_tmp" / "sfx_feat.json"
SR = 22050
REFS = ["휙1.mp3", "휙２.mp3", "SEL_ゲージ回復1.mp3", "KN_pepSound1.wav", "채팅 효과음.mp3", "맑은소리.mp3"]
ROLE_REF = {"확대": ["휙1.mp3", "휙２.mp3"], "전환": ["휙1.mp3", "휙２.mp3"],
            "표시": ["SEL_ゲージ回復1.mp3", "맑은소리.mp3"], "반짝": ["맑은소리.mp3", "SEL_ゲージ回復1.mp3"],
            "등장": ["KN_pepSound1.wav", "채팅 효과음.mp3"], "메시지": ["채팅 효과음.mp3"],
            "귀여움": ["KN_pepSound1.wav"], "확정": ["맑은소리.mp3", "SEL_ゲージ回復1.mp3"]}
KEYS = ["dur", "attack", "decay", "centroid", "rolloff", "low", "mid", "high", "air", "flat", "crest"]
LOGK = {"dur", "attack", "decay", "centroid", "rolloff"}
WEIGHT = {"centroid": 1.5, "rolloff": 1.0, "high": 1.2, "air": 1.2, "flat": 1.2, "crest": 1.0,
          "dur": 0.8, "attack": 1.0, "decay": 0.8, "low": 0.8, "mid": 0.8}


def _pcm(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def features(path):
    x = _pcm(path)
    if len(x) < SR // 50:
        return None
    hop = SR // 100                                         # 10ms
    n = len(x) // hop
    env = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    pk = env.max()
    on = np.where(env > pk - 50)[0]
    if not len(on):
        return None
    a, b = on[0], on[-1] + 1
    x = x[a * hop:b * hop]
    env = env[a:b]
    ip = int(env.argmax())
    after = np.where(env[ip:] < pk - 20)[0]
    f = {"dur": len(x) / SR, "attack": ip * 0.01 + 0.005,
         "decay": (after[0] if len(after) else len(env) - ip) * 0.01 + 0.005}
    nfft = 2048
    if len(x) < nfft:
        x = np.pad(x, (0, nfft - len(x)))
    fr = np.lib.stride_tricks.sliding_window_view(x, nfft)[::512] * np.hanning(nfft)
    S = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    w = S.sum(1)
    S = S[w > w.max() * 1e-3]                               # 조용한 프레임 빼고
    P = S.sum(0) + 1e-12
    fq = np.fft.rfftfreq(nfft, 1 / SR)
    f["centroid"] = float((fq * P).sum() / P.sum())
    c = np.cumsum(P) / P.sum()
    f["rolloff"] = float(fq[np.searchsorted(c, 0.85)])
    tot = P.sum()
    f["low"] = float(P[fq < 250].sum() / tot)
    f["mid"] = float(P[(fq >= 250) & (fq < 2000)].sum() / tot)
    f["high"] = float(P[(fq >= 2000) & (fq < 6000)].sum() / tot)
    f["air"] = float(P[fq >= 6000].sum() / tot)
    gm = np.exp(np.log(S + 1e-12).mean(1))
    f["flat"] = float(np.median(gm / (S.mean(1) + 1e-12)))
    f["crest"] = float(20 * np.log10(np.abs(x).max() / (np.sqrt((x ** 2).mean()) + 1e-9)))
    return f


def _load_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def table(paths):
    """{경로: 특징} — 캐시(경로·크기·수정 시각)를 쓴다."""
    cache, out, dirty = _load_cache(), {}, False
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        st = p.stat()
        k = p.as_posix()
        e = cache.get(k)
        if not e or e.get("_sig") != [st.st_size, int(st.st_mtime)]:
            ft = features(p)
            if ft is None:
                continue
            e = dict(ft, _sig=[st.st_size, int(st.st_mtime)])
            cache[k], dirty = e, True
        out[k] = e
    if dirty:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return out


def library_paths():
    man = json.loads((LIB / "_manifest.json").read_text(encoding="utf-8"))["entries"]
    return [LIB / e["file"] for e in man] + [LOCAL / r for r in REFS]


class Feel:
    """라이브러리 전체로 표준화한 공간에서 기준과의 거리."""

    def __init__(self):
        self.t = table(library_paths())
        M = np.array([self._raw(v) for v in self.t.values()])
        self.mu, self.sd = M.mean(0), M.std(0) + 1e-9
        self.ref = {r: self._z(self.t[(LOCAL / r).as_posix()]) for r in REFS if (LOCAL / r).as_posix() in self.t}
        # 기준끼리 거리 → «가까움/멂» 문턱(라이브러리 전체 거리 분포의 분위)
        allz = [self._z(v) for v in self.t.values()]
        d = np.array([min(self._d(z, rz) for rz in self.ref.values()) for z in allz])
        self.near, self.far = float(np.percentile(d, 25)), float(np.percentile(d, 70))

    def _raw(self, f):
        return np.array([np.log(max(f[k], 1e-4)) if k in LOGK else f[k] for k in KEYS])

    def _z(self, f):
        return (self._raw(f) - self.mu) / self.sd

    def _d(self, a, b):
        w = np.array([WEIGHT[k] for k in KEYS])
        return float(np.sqrt((w * (a - b) ** 2).sum() / w.sum()))

    def dist(self, path, role=None):
        k = Path(path).as_posix()
        f = self.t.get(k) or table([path]).get(k)
        if f is None:
            return None, None
        z = self._z(f)
        refs = ROLE_REF.get(role) or list(self.ref)
        best = min(((self._d(z, self.ref[r]), r) for r in refs if r in self.ref), default=(None, None))
        return best

    def grade(self, d):
        if d is None:
            return "?"
        return "가까움" if d <= self.near else ("멂" if d > self.far else "보통")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fe = Feel()
    print(f"문턱: 가까움 ≤ {fe.near:.2f} · 멂 > {fe.far:.2f} (라이브러리 {len(fe.t)}개 기준 25·70분위)")
    for a in sys.argv[1:]:
        if a.endswith(".json"):
            plan = json.loads(Path(a).read_text(encoding="utf-8"))
            items = [(fx["file"], fx.get("_역할", "")) for fx in plan.get("sfx", [])]
        else:
            items = [(a, "")]
        for fp, role in items:
            d, r = fe.dist(fp)
            print(f"  {fe.grade(d):3s} {d if d is None else round(d, 2)} (닮은 기준 {r}) · {Path(fp).name} · {role}")


if __name__ == "__main__":
    main()
