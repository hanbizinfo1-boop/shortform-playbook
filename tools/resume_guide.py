# -*- coding: utf-8 -*-
"""SessionStart 훅(startup·compact·resume) — 자동 압축·세션 재개 뒤에도 규칙을 빠뜨리지 않게, 상시 규칙과 지금 진행 상황을 대화에 넣는다.

근거: 사장님 10-07 «오토컴팩트 진행되더라도 길라잡이 누락되지 않게끔 장치 만들어서 적용»(원본 D:/영상제작/도구/점검/resume_guide.py,
쇼츠광고·롱폼자동화 저장소에 같은 훅이 있다 — 이 파일은 이 저장소용으로 새로 쓴 것이다).
.claude/settings.json → hooks.SessionStart → python tools/resume_guide.py
출력(표준 출력)이 그대로 대화 맥락에 들어간다. 발췌만 믿지 말고 SKILL.md 와 references/ 를 다시 연다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "shortform" / "SKILL.md"
RECORD = ROOT / "기록" / "작업기록.md"
LIMIT = 7000  # 대화에 넣는 최대 글자 수
NOW_ITEMS, NOW_CHARS = 3, 500   # «지금 상태»는 최근 건만 짧게(전문은 파일) — 길어지면 상시 규칙이 잘려 들어갔다(10-14)


def section(text, keyword):
    """'## ... 키워드 ...' 절을 다음 '## ' 직전까지 잘라 온다."""
    m = re.search(rf"^## [^\n]*{re.escape(keyword)}[^\n]*\n[\s\S]*?(?=\n## |\Z)", text, re.M)
    return m.group(0).strip() if m else ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = ["# 숏폼 자동화 — 세션 재개 자동 안내 (작업 전에 아래를 다시 읽는다)", ""]
    # 순서가 곧 우선순위다 — 넘치면 뒤가 잘린다.
    # 10-14: 예전엔 «지금 상태»(5천 자)가 먼저라 상시 규칙이 중간에서 잘려 들어갔다 → 규칙을 먼저, 진행 상황은 최근 건만 짧게
    if SKILL.exists():
        t = SKILL.read_text(encoding="utf-8")
        for kw in ("상시 규칙", "멈추는 곳"):
            s = section(t, kw)
            if s:
                out.append(s)
    if RECORD.exists():
        r = RECORD.read_text(encoding="utf-8")
        now = section(r, "지금 상태")
        if now:
            body = now.split("\n", 1)[1] if "\n" in now else ""
            items = re.split(r"\n(?=- )", body)
            items = [i.strip() for i in items if i.strip().startswith("- ")][:NOW_ITEMS]
            items = [i if len(i) <= NOW_CHARS else i[:NOW_CHARS] + " …" for i in items]
            out.append("## 지금 상태 (최근 %d건 발췌 — 전문 `기록/작업기록.md`)\n" % len(items) + "\n".join(items))
        nxt = section(r, "다음 작업 예정")
        if nxt:
            out.append(nxt)
    footer = ("\n\n---\n위는 발췌다(넘치면 잘린다). 읽을 순서: CLAUDE.md → .claude/skills/shortform/SKILL.md"
              "(1장 표에서 지금 일의 references/) → 기록/작업기록.md — 파일을 Read 로 다시 열어 전문을 확인한 뒤 이어 간다.")
    text = "\n\n".join(out)
    if len(text) > LIMIT - len(footer):
        text = text[:LIMIT - len(footer)] + "\n…(잘림 — 파일을 직접 연다)"
    print(text + footer)


if __name__ == "__main__":
    main()
