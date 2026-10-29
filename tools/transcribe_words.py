# -*- coding: utf-8 -*-
"""롱폼 음성 → 단어 시각 전사(faster-whisper). 쇼츠 구간 고르기·자막의 원자료.

    python tools/transcribe_words.py <음성.wav> <출력폴더> [--model large-v3] [--cpu] [--offset 초]

출력: words.json(문장마다 start·end·text·words[{s,e,w}]) · transcript.md(«[mm:ss] 문장» 한 줄씩, 정독용)
기본 GPU large-v3(int8_float16), 실패하면 CPU medium 으로 자동 전환. --cpu 로 CPU 강제. 한국어 고정, VAD 켬.
GPU: pip `nvidia-cublas-cu12` · `nvidia-cudnn-cu12==9.*`(10-13 설치) — 그 DLL 폴더를 아래에서 등록한다. CPU 는 `--model medium --cpu`.
"""
import json
import os
import site
import sys
from pathlib import Path

# pip 로 깐 cuBLAS·cuDNN DLL 을 Windows 가 찾도록 등록(없으면 cuda 가 cublas64_12.dll 오류)
for sp in site.getsitepackages():
    for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
        d = Path(sp) / sub
        if d.is_dir():
            os.add_dll_directory(str(d))
            os.environ["PATH"] = str(d) + os.pathsep + os.environ["PATH"]

from faster_whisper import WhisperModel  # noqa: E402


def mmss(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    src, out = Path(a[0]), Path(a[1])
    model = a[a.index("--model") + 1] if "--model" in a else "large-v3"
    cpu = "--cpu" in a
    off = float(a[a.index("--offset") + 1]) if "--offset" in a else 0.0  # 잘라 낸 음성의 원본 시작 초
    out.mkdir(parents=True, exist_ok=True)
    opts = dict(language="ko", word_timestamps=True, vad_filter=True, beam_size=5, condition_on_previous_text=False)
    if not cpu:
        try:  # GPU 기본 — 라이브러리·메모리 문제면 CPU medium 으로 자동 전환
            m = WhisperModel(model, device="cuda", compute_type="int8_float16")
            segs, info = m.transcribe(str(src), **opts)
            segs = list(segs)
            print(f"장치: GPU({model})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"GPU 실패 → CPU medium 으로 전환: {e}", flush=True)
            cpu, model = True, "medium"
    if cpu:
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, info = m.transcribe(str(src), **opts)
        print(f"장치: CPU({model})", flush=True)
    rows, lines = [], []
    for s in segs:
        words = [{"s": round(w.start + off, 2), "e": round(w.end + off, 2), "w": w.word} for w in (s.words or [])]
        rows.append({"start": round(s.start + off, 2), "end": round(s.end + off, 2), "text": s.text.strip(), "words": words})
        lines.append(f"[{mmss(s.start + off)}] {s.text.strip()}")
        print(lines[-1], flush=True)
    (out / "words.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"완료 문장 {len(rows)}개 · 길이 {info.duration:.1f}초")


if __name__ == "__main__":
    main()
