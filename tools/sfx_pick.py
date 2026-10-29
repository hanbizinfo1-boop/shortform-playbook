# -*- coding: utf-8 -*-
"""효과음 후보 고르기 — 역할별로 라이브러리에서 «이 편에서 아직 덜 쓴» 파일을 돌려 가며 낸다.

    python tools/sfx_pick.py <역할> [--plan <계획.json>] [--n 6]
    역할: 확대 | 전환 | 표시 | 등장 | 확정 | 허수 | 메시지 | 반짝 | 코믹 | 놀람 | 귀여움 | 강조 | 긴장 | 웃음

근거: 사장님 10-14 «효과음 그냥 너무 반복되는데?» — 이 저장소에 효과음이 6개뿐이라 같은 소리를 돌려 썼다.
라이브러리(읽기 전용) = D:/영상제작/소재/예능효과음 (분류 폴더 19개 · `_manifest.json` 674개 · 라이선스 기록).
채널 강의 쇼츠는 코믹·놀람·귀여움도 영상에 어울리면 쓴다(10-14). 마림바·실로폰만 늘 뺀다.
등급표(D:/영상제작/길라잡이/예능효과음-등급.json)는 파일 경로가 옛 PC(작업공간) 기준이라 쓰지 않는다.
10-15: 후보를 «통과한 효과음과 결이 닮은 순»으로 — `tools/sfx_feel.py`(설계자는 소리를 못 듣는다 → 높낮이·길이·터지는 세기로 거름).
    같은 횟수면 가까움 > 보통 > 멂, 그 안에서 거리 순. «멂»은 맨 뒤.
"""
import json
import sys
from collections import Counter
from pathlib import Path

LIB = Path("D:/영상제작/소재/예능효과음")
LOCAL = Path(__file__).resolve().parents[1] / "소재" / "효과음"
ROLE = {                                   # 역할 → 분류 폴더(앞쪽이 먼저)
    "확대": ["10_휙_전환"],
    "전환": ["10_휙_전환"],
    "표시": ["03_띵_딩", "02_뿅_팝"],
    "등장": ["02_뿅_팝", "03_띵_딩"],
    "확정": ["05_띵동_정답성공"],
    "허수": ["06_실패_오답"],
    "메시지": ["16_UI_타자_메시지"],
    "반짝": ["04_반짝_띠링"],
    "코믹": ["15_코믹동작"],
    "놀람": ["07_띠용_놀람"],
    "귀여움": ["08_귀여움_방울"],
    "강조": ["01_쿵쾅_큰강조자막"],
    "긴장": ["09_긴장_두근"],
    "웃음": ["14_웃음_박수_환호"],
}
# 10-14 사장님 «코믹 놀람 귀여움 써도돼 영상에만 어울리면» — 채널 강의 쇼츠는 분류로 막지 않는다(어울리는지는 고르는 쪽이 판단).
# 광고 모션그래픽의 «게임·마법·코믹 금지»(10-12)는 광고 범위 규칙 — SKILL 5장
BANNED = set()
BAN_WORDS = ("marimba", "xylophone", "실로폰", "마림바")     # 사장님이 직접 싫다고 한 소리(«실리폰소리 되게 듣기싫»)만 늘 뺀다


def used_counts(plan_path):
    if not plan_path:
        return Counter()
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    return Counter(Path(f["file"]).name for f in plan.get("sfx", []))


def candidates(role, used, n=6, max_dur=1.2):
    man = json.loads((LIB / "_manifest.json").read_text(encoding="utf-8"))["entries"]
    from sfx_feel import Feel
    fe = Feel()
    out = []
    for folder in ROLE[role]:
        if folder in BANNED:
            continue
        rows = [e for e in man if e["file"].startswith(folder + "/") and (e.get("dur") or 0) <= max_dur]
        rows.sort(key=lambda e: (used[Path(e["file"]).name], e.get("dur") or 0))
        for e in rows:
            p = LIB / e["file"]
            if any(w in p.name.lower() for w in BAN_WORDS):      # 마림바·실로폰
                continue
            if p.exists():
                d, ref = fe.dist(p, role)
                out.append((used[p.name], p, e.get("dur"), e.get("license", ""), d, ref, fe.grade(d)))
    rank = {"가까움": 0, "보통": 1, "?": 2, "멂": 3}
    out.sort(key=lambda r: (r[0], rank[r[6]], r[4] if r[4] is not None else 9))
    return out[:n]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a or a[0] not in ROLE:
        print("역할:", " | ".join(ROLE))
        return
    plan = a[a.index("--plan") + 1] if "--plan" in a else None
    n = int(a[a.index("--n") + 1]) if "--n" in a else 6
    used = used_counts(plan)
    for k, p, dur, lic, d, ref, g in candidates(a[0], used, n):
        print(f"  결 {g}({d:.2f}, 닮은 기준 {ref}) · 이미 {k}회 · {dur}s · {lic} · {p.as_posix()}")


if __name__ == "__main__":
    main()
