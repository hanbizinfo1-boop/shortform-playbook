# 템플릿 서랍 — 규격 (지금 0개)

서랍 체계·계승 후보·고르는 법은 `.claude/skills/shortform/references/drawers.md`. 이 폴더는 템플릿 실물이 쌓이는 곳이다.
원형: 롱폼 `templates/README.md` · `auto-pipeline.md` 3장(사장님 10-08 지시). 텍스트·코드만 커밋하고 견본 렌더는 `_tmp/`.

## 폴더 하나 = 템플릿 하나

```
templates/<ID>_<영문이름>/        예: SC-01_list_highlight/
  template.json   매니페스트
  render.py | scene.html | build.jsx   엔진 소스(파라미터 칸만 비워 둔 것)
  sample/         견본 입력(json) — 견본 렌더 mp4·정지는 _tmp/templates/<ID>/
  history.json    쓰인 건·컷·통과/반려(원문)·점수
```

## template.json

```json
{
  "id": "SC-01", "name": "정렬 목록 + 지금 것 형광펜", "drawer": "SC", "version": 1,
  "engine": "html",
  "situations": ["SP-08", "SP-10"],
  "use_when": ["여러 항목 나열", "회사가 해 주는 것"],
  "avoid_when": ["항목 2개 이하", "비교"],
  "format": "1080x1920", "layer": "overlay", "alpha": true,
  "duration": [2, 8],
  "slots": {
    "items": {"kind": "text_list", "max_items": 8, "max_chars": 10, "rule": "원문·개념어, 말 복사 금지"},
    "bg":    {"kind": "image", "source": ["doc", "codex", "real_capture"], "per_item": true}
  },
  "drawn_allowed": ["형광펜", "카드 바탕", "구분선"],
  "keepout": ["caption", "fixed_bars", "person"],
  "sfx_roles": ["montage_tick", "highlight"],
  "beats": "항목마다 1박 이상, 형광펜 4프레임",
  "status": "신규",
  "passed": [], "rejected": [],
  "from": "한비즈-쇼츠광고/tools/scenes/html/hanbiz_3an_typo.html (3안 2판, 10-12)"
}
```

- `status`: 신규 → 시안 → 대기(만들었지만 반응 없음) → 통과(사장님 원문). 다른 저장소에서 통과했어도 이 저장소에서는 **대기**로 시작한다.
- 이미지 칸 `source` 허용: `codex` · `crawl`(공식·위키미디어, 출처 필수) · `real_capture` · `brand` · `char2d` · `doc`(실제 견본·자료) · `aivideo`(유료, 한도 안에서만). 사물을 도형으로 그리는 템플릿은 등록하지 않는다.
- `rejected` 에는 사장님 원문을 그대로. 같은 이유 반려 2번이면 그 상황을 `avoid_when` 에.
- 등록 검사 도구: ☐ 롱폼 `tools/auto/registry.py` 를 세로 규격으로 이식(카탈로그 자동 생성).
