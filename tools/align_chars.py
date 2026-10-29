# -*- coding: utf-8 -*-
"""대본 글자 ↔ 목소리 강제 정렬(CTC forced alignment) — 자막 시각의 정본 (10-14 «자막이랑 목소리 나오는 타이밍 정확도»).

전사(whisper) 단어 시각은 앞 숨을 먹거나 이어 말하는 중간에 찍혀 0.2~0.6초 틀릴 때가 있고, 음량 쉼만으로는 어느 쉼이
자막 경계인지 모른다. 그래서 «이미 아는 글자»를 소리에 맞춰 음절마다 시각을 찍는다(20ms 단위).
모델: kresnik/wav2vec2-large-xlsr-korean(음절 1,205개 + | 단어 경계, HF 캐시에 있음). 숫자·영문은 [UNK] 로 맞춘다.

    align(path, t0, t1, texts) → [[(글자, 시작초, 끝초), ...] (texts 마다)]   — 한글 음절 + 숫자·영문 덩어리(«#»)
"""
import glob
import json
import subprocess
from pathlib import Path

import numpy as np

_M = {}


def _model():
    if not _M:
        import torch
        from transformers import Wav2Vec2ForCTC
        snap = glob.glob(str(Path.home() / ".cache/huggingface/hub/models--kresnik--wav2vec2-large-xlsr-korean/snapshots/*"))[0]
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        m = Wav2Vec2ForCTC.from_pretrained(snap).to(dev).eval()
        vocab = json.load(open(Path(snap) / "vocab.json", encoding="utf-8"))
        _M.update(m=m, vocab=vocab, dev=dev)
    return _M


def _audio(path, t0, t1, sr=16000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(path),
                          "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def align(path, t0, t1, texts):
    import torch
    import torchaudio.functional as F
    M = _model()
    vocab, unk, pad, sep = M["vocab"], M["vocab"]["[UNK]"], M["vocab"]["[PAD]"], M["vocab"]["|"]
    x = _audio(path, t0, t1)
    x = (x - x.mean()) / (x.std() + 1e-7)
    with torch.inference_mode():
        lp = torch.log_softmax(M["m"](torch.from_numpy(x)[None].to(M["dev"])).logits.float(), -1).cpu()
    spf = (t1 - t0) / lp.shape[1]                  # 프레임당 초(≈0.02)
    # 글자열 → 토큰(음절 · [UNK] · 단어 경계 |). owner 로 어느 자막 몇 번째 글자인지 기억
    tokens, owner = [], []
    for ti, t in enumerate(texts):
        for wi, word in enumerate(t.split()):
            if tokens:
                tokens.append(sep)
                owner.append(None)
            prev_unk = False
            for ci, ch in enumerate(word):
                if "가" <= ch <= "힣":
                    tokens.append(vocab.get(ch, unk))
                    owner.append((ti, wi, ci, ch))
                    prev_unk = False
                elif ch.isalnum() and not prev_unk:     # 숫자·영문 덩어리 하나 = [UNK] 하나(시각은 «#» 로 돌려줌)
                    tokens.append(unk)
                    owner.append((ti, wi, ci, "#"))
                    prev_unk = True
    if not tokens:
        return [[] for _ in texts]
    ali, _ = F.forced_align(lp, torch.tensor([tokens], dtype=torch.int32), blank=pad)
    spans = F.merge_tokens(ali[0], torch.zeros(ali.shape[1]), blank=pad)   # blank 기본값 0 은 음절 하나라 꼭 지정
    out = [[] for _ in texts]
    for k, sp in enumerate(spans):
        if k < len(owner) and owner[k] is not None:
            ti, wi, ci, ch = owner[k]
            out[ti].append((ch, t0 + sp.start * spf, t0 + sp.end * spf))
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    src, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    for row in align(src, a, b, sys.argv[4:]):
        print(" ".join(f"{c}{s:.2f}" for c, s, e in row))
