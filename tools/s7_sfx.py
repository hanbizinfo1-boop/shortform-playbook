# -*- coding: utf-8 -*-
"""S7 — 계획의 "sfx"(샷 번호 + 박자 이름)를 렌더된 props 의 출력 시각으로 바꿔 sfx_overlay 큐를 만들고 섞는다.

    python tools/s7_sfx.py <계획.json>

계획 "sfx": [{"shot": 샷 번호(0부터), "beat": 박자 이름 | 숫자(샷 안 초), "add": 더할 초, "file": 경로, "rel": dB, "align": "peak", "series": 묶음, "max": 초, "_뜻": 메모}]
  박자는 s7_prep 이 강제 정렬로 잡은 그 낱말의 소리 시각 → 소리가 그림 사건(같은 박자)과 같은 프레임에 붙는다.
출력: <out>.mp4 를 같은 이름으로 덮어씀(효과음 없는 판은 _tmp/s7/<이름>_무음효과.mp4 로 옮겨 둠).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    job = Path(plan["out"]).name
    props = json.loads((ROOT / "tools/remotion2d/public" / job / "props.json").read_text(encoding="utf-8"))
    shots = props["shots"]
    cues = []
    for c in plan["sfx"]:
        sh = shots[c["shot"]]
        b = c.get("beat", 0)
        if isinstance(b, str) and b.startswith("__seg"):   # 플래시 몽타주 n번째 칸 시작
            lt = int(b[5:]) * (sh["end"] - sh["start"]) / len(sh["p"]["refs"])
        else:
            lt = sh["beats"][b] if isinstance(b, str) else b
        t = sh["start"] + lt + c.get("add", 0)
        cue = {k: v for k, v in c.items() if k in ("file", "rel", "align", "series", "max", "pre", "_뜻")}
        cue["at"] = round(t, 3)
        cues.append(cue)
    cues.sort(key=lambda x: x["at"])
    mp4 = ROOT / (plan["out"] + ".mp4")
    keep = ROOT / "_tmp" / "s7" / f"{job}_무음효과.mp4"
    if not keep.exists():   # s7_prep 이 렌더할 때 효과음 없는 판을 여기 둔다 — 다시 섞어도 효과음이 겹치지 않게
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(mp4, keep)
    q = {"src": str(keep), "out": str(mp4), "sfx": cues}
    if plan.get("bgm"):
        q["bgm"] = plan["bgm"]
    qp = ROOT / "_tmp" / "s7" / f"{job}_큐.json"
    qp.write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"큐 {len(cues)}개 → {qp}")
    subprocess.run([sys.executable, str(ROOT / "tools" / "sfx_overlay.py"), str(qp)], check=True)


if __name__ == "__main__":
    main()
