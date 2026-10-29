# -*- coding: utf-8 -*-
"""직원 공유용 공개본 만들기 — 허용 목록만 복사 → 민감어 가림 → 남은 민감어가 있으면 멈춤.

    python tools/export_public.py            # → _tmp/public/ (git 저장소는 그 안에서 따로 관리)

10-29 사장님 «지금까지 우리가 한 모든 노하우 … 직원들에게 공유 … 깃헙에 다 정리해서 커밋해주고 공개로»
→ 선택 «공개, 민감한 건 빼고»: 고객·현장 자료, 사람 이름, 피드백 원문 로그, 작업기록, 영업 구조, 계승노트는 뺀다.
원본 작업 저장소(이 폴더)는 private 그대로 — 히스토리에 내부 자료가 있어서 공개본은 따로 만든다.
"""
import fnmatch
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "_tmp" / "public"
HOME_CLAUDE = Path.home() / ".claude"

INCLUDE = [
    "CLAUDE.md", "이어하기.ps1", ".gitattributes",
    ".claude/settings.json", ".claude/skills/shortform/**",
    "tools/*.py", "tools/README.md", "tools/scenes/*.py", "tools/ae/*.jsx",
    "tools/remotion2d/src/*", "tools/remotion2d/package.json", "tools/remotion2d/package-lock.json",
    "tools/remotion2d/tsconfig.json", "tools/remotion2d/.gitignore",
    "templates/**",
    "소재/fonts/*.otf", "소재/ai/**/*.png",
    "기록/빡이사DB_계획/*.json", "기록/빡이사DB_쇼츠편성_1013.md", "기록/조사_*.md", "기록/레퍼해부/**",
]
EXCLUDE = [".claude/skills/shortform/references/feedback-log.md", "**/__pycache__/**"]
TEXT = {".md", ".json", ".py", ".ps1", ".jsx", ".txt", ".gitattributes", ".gitignore"}

# 가림(모든 텍스트 파일) — 사람 이름·고객 현장·예시로 남은 실제 상호
REPLACE = [
    (r"○○", "○○"),
    (r"○○캐피탈", "○○캐피탈"),
    (r"대우 ?○○ 아파트", "○○ 아파트"), (r"○○ 아파트", "○○ 아파트"), (r"○○", "○○"),
    (r"○○역", "○○역"), (r"○○동", "○○동"), (r"○○", "○○"),
]
- (내부 영업 구조 — 공개본에서 뺐다)
- (내부 영업 구조 — 공개본에서 뺐다)
DROP_NOTE = "- (내부 영업 구조 — 공개본에서 뺐다)"
# 공개본에 남으면 안 되는 것
- (내부 영업 구조 — 공개본에서 뺐다)
                    r"(?<![0-9])0(?:1[016789]|2|[3-6][1-5])-?(?!0000)[0-9]{3,4}-[0-9]{4}(?![0-9])")

OFL = """Copyright (c) 2021, Kil Hyung-jin (https://github.com/orioncactus/pretendard),
with Reserved Font Name Pretendard.

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
https://openfontlicense.org

-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide development of collaborative font projects, to support the font creation efforts of academic and linguistic communities, and to provide a free and open framework in which fonts may be shared and improved in partnership with others.

The OFL allows the licensed fonts to be used, studied, modified and redistributed freely as long as they are not sold by themselves. The fonts, including any derivative works, can be bundled, embedded, redistributed and/or sold with any software provided that any reserved names are not used by derivative works. The fonts and derivatives, however, cannot be released under any other type of license. The requirement for fonts to remain under this license does not apply to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright Holder(s) under this license and clearly marked as such. This may include source files, build scripts and documentation.
"Reserved Font Name" refers to any names specified as such after the copyright statement(s).
"Original Version" refers to the collection of Font Software components as distributed by the Copyright Holder(s).
"Modified Version" refers to any derivative made by adding to, deleting, or substituting -- in part or in whole -- any of the components of the Original Version, by changing formats or by porting the Font Software to a new environment.
"Author" refers to any designer, engineer, programmer, technical writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining a copy of the Font Software, to use, study, copy, merge, embed, modify, redistribute, and sell modified and unmodified copies of the Font Software, subject to the following conditions:
1) Neither the Font Software nor any of its individual components, in Original or Modified Versions, may be sold by itself.
2) Original or Modified Versions of the Font Software may be bundled, redistributed and/or sold with any software, provided that each copy contains the above copyright notice and this license. These can be included either as stand-alone text files, human-readable headers or in the appropriate machine-readable metadata fields within text or binary files as long as those fields can be easily viewed by the user.
3) No Modified Version of the Font Software may use the Reserved Font Name(s) unless explicit written permission is granted by the corresponding Copyright Holder. This restriction only applies to the primary font name as presented to the users.
4) The name(s) of the Copyright Holder(s) and the Author(s) of the Font Software shall not be used to promote, endorse or advertise any Modified Version, except to acknowledge the contribution(s) of the Copyright Holder(s) and the Author(s) or with their explicit written permission.
5) The Font Software, modified or unmodified, in part or in whole, must be distributed entirely under this license, and must not be distributed under any other license. The requirement for fonts to remain under this license does not apply to any document created using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM OTHER DEALINGS IN THE FONT SOFTWARE.
"""

FEEDBACK_STUB = """# 사장님 피드백 원문 로그 — 공개본에서는 비움

원본 작업 저장소에는 사장님 말씀을 **원문 그대로** 한 줄씩 남긴다(`CLAUDE.md` 하드 규칙 7). 공개본에서는 내부 대화라 뺐다.
규칙의 근거가 된 짧은 인용(«…»)은 `SKILL.md`·`references/` 안에 남아 있다.

기록 형식(내 작업 저장소에서 이어 쓸 때):

| 날짜 | 편·주제 | 원문(그대로) | 이렇게 바꿨다(규칙 한 줄) |
|---|---|---|---|
"""

GITIGNORE = """_tmp/*
!_tmp/.gitkeep
납품/
*.mp4
*.mov
*.avi
*.mkv
*.webm
*.wav
*.mp3
*.m4a
*.aac
*.flac
*.aep
*.aepx
*.prproj
*.psd
*.key
*.pem
.env
desktop.ini
Thumbs.db
.vscode/
__pycache__/
*.pyc
.venv/
.claude/settings.local.json
"""


def wanted(rel):
    if any(fnmatch.fnmatch(rel, p) for p in EXCLUDE):
        return False
    return any(fnmatch.fnmatch(rel, p) for p in INCLUDE)


def scrub(text, rel):
    out = []
    for line in text.split("\n"):
        if DROP_LINE.search(line):
            if line.lstrip().startswith("|"):
                continue                                   # 표 줄은 통째로 뺀다
            out.append(DROP_NOTE)
            continue
        out.append(line)
    text = "\n".join(out)
    for a, b in REPLACE:
        text = re.sub(a, b, text)
    if rel == "CLAUDE.md":
        text = re.sub(r"(?m)^- 이 저장소는 \*\*private\*\*.*$",
                      "- 이 저장소는 **공개본**이다(`tools/export_public.py` 로 만든다 — 원본 작업 저장소는 private). "
                            "고객·현장 자료·사람 이름·피드백 원문·영업 구조·계정·계약 금액은 넣지 않는다.", text)
        text = re.sub(r"원격: `origin` → .*\n", "원격: 각자 쓰는 저장소. 공개본은 원본 저장소의 `tools/export_public.py` 로 다시 만든다.\n", text)
    return text


def write(rel, data):
    p = DST / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8", newline="\n")
    else:
        p.write_bytes(data)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if DST.exists():
        for c in DST.iterdir():
            if c.name != ".git":
                shutil.rmtree(c) if c.is_dir() else c.unlink()
    DST.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(ROOT.rglob("*")):
        if not f.is_file() or "_tmp" in f.parts or ".git" in f.parts:
            continue
        rel = f.relative_to(ROOT).as_posix()
        if not wanted(rel):
            continue
        if f.suffix in TEXT or f.name in TEXT:
            write(rel, scrub(f.read_text(encoding="utf-8-sig" if f.suffix == ".ps1" else "utf-8"), rel)
                  if f.suffix != ".ps1" else f.read_bytes())
        else:
            write(rel, f.read_bytes())
        n += 1
    # README = 직원 가이드
    guide = scrub((ROOT / "직원가이드.md").read_text(encoding="utf-8"), "README.md")
    write("README.md", guide)
    write("직원가이드.md", guide)
    write(".claude/skills/shortform/references/feedback-log.md", FEEDBACK_STUB)
    write("소재/fonts/OFL.txt", OFL)
    write(".gitignore", GITIGNORE)
    write("_tmp/.gitkeep", "")
    # 하네스(~/.claude) 사본
    for src, rel in ((HOME_CLAUDE / "CLAUDE.md", "harness/CLAUDE.md"),
                     (HOME_CLAUDE / "scripts" / "codex-run.ps1", "harness/scripts/codex-run.ps1")):
        if src.exists():
            write(rel, src.read_bytes())
    for a in sorted((HOME_CLAUDE / "agents").glob("*.md")):
        write(f"harness/agents/{a.name}", scrub(a.read_text(encoding="utf-8"), a.name))
    # sfx_overlay 큐 예시(분양 현장 → ○○)
    ex = ROOT / "기록" / "○○역_효과음" / "2차_v3.json"
    if ex.exists():
        d = json.loads(scrub(ex.read_text(encoding="utf-8"), "ex"))
        d["src"] = "D:/<날짜>/<원본 영상>.mp4"
        d["out"] = "C:/Users/<나>/Desktop/숏폼자동화/납품/<건>/<원본>_효과음.mp4"
        d["_설명"] = ("분양 광고 쇼츠 2차(44.9초) 실제 큐 — 효과음 38·장면음 13·BGM. 현장 이름은 ○○로 가림. "
                    "at 은 그림이 처음 보이는 프레임(30fps 띠로 잼), rel 은 목소리 대비 dB, series 는 같은 그림 열거 통일.")
        write("examples/sfx_overlay_큐_예시.json", json.dumps(d, ensure_ascii=False, indent=1))
    # 남은 민감어 검사 — 하나라도 있으면 실패
    bad = []
    for f in DST.rglob("*"):
        if f.is_file() and ".git" not in f.parts and (f.suffix in TEXT or f.name in TEXT):
            for i, line in enumerate(f.read_text(encoding="utf-8-sig", errors="replace").split("\n"), 1):
                m = BANNED.search(line)
                if m and "010-0000-0000" not in m.group(0):
                    bad.append(f"{f.relative_to(DST).as_posix()}:{i}: {m.group(0)}")
    print(f"공개본 {DST} · 원본에서 {n}개 + 가이드·하네스·예시")
    if bad:
        print("[ERROR] 민감어가 남았다 — 공개 금지:")
        print("\n".join(bad[:50]))
        sys.exit(1)
    print("민감어 검사 통과")


if __name__ == "__main__":
    main()
