# 계승 출처 — 무엇을 어디서 읽고 무엇을 가져왔나 (2026-10-13)

사장님 지시(10-13): «지금 롱폼자동화, 쇼츠광고, 영상제작 이 3개의 세션과 레포에서 작업한 작업로그, 학습한 학습로그, 경험데이터 , 워크플로우 설계구조 하나하나 정독(대충보고 참고했다는게아니라 제대로 처음부터 끝까지 내용을 보라는뜻)해서 숏폼 자동화 학습전 뼈대를 만들어».
세 저장소는 **읽기만** 했다(수정 없음). 세 곳 모두 서로 독립 저장소라(10-08 «이제는 독립적으로 갈거야») 이 저장소도 독립이다 — 원본과 동기화하지 않고, 필요한 규칙은 이 폴더로 옮겨 적는다.

## 1. 읽은 범위

### 설계자(이 세션)가 처음부터 끝까지 직접 읽은 것

| 저장소 | 파일 |
|---|---|
| 한비즈-롱폼자동화 | `CLAUDE.md` · `README.md` · `기록/작업기록.md` · `SKILL.md` · `references/auto-pipeline.md` · `situation-playbook.md` · `feedback-log.md` · `checklist.md` · `content-cut.md` · `silence-cut.md` · `sfx-workflow.md` · `lecture-graphics.md` · `motion-graphics.md` · `tones/TN-1~4.json`(앞부분) |
| 한비즈-쇼츠광고 | `CLAUDE.md` · `README.md` · `기록/작업기록.md` · `SKILL.md` · `references/workflow.md` · `feedback-log.md`(209줄) · `checklist.md` · `techniques.md` · `motion-typo.md` · `editing-premiere.md` · `sfx.md`(535줄) · `motion-graphics.md` · `design-paths.md` · `ai-video.md` · `blender.md` · `study/README.md` · `.claude/settings.json` · `tools/resume_guide.py` |
| D:\영상제작 | `CLAUDE.md` · `길라잡이/README.md` · `문서지도.md` · `작업-재개-필독.md` · `작업차선.md` · `정본-작업방식.md` · `제작규칙-길라잡이.md` |
| 세션 기록 | 세 저장소 세션 10개(jsonl 약 900MB, 대부분 이미지)에서 **사장님 발언 전량**을 뽑아 전부 읽음(약 190KB — 영상제작 7개·쇼츠광고 2개·롱폼 1개, 자동 요약 블록 제외) |
| 메모리 | `~/.claude/projects/D------/memory/` 30건 전부 · 홈 메모리 4건 |

### 실행 에이전트 5명이 정독·추출하고 설계자가 검수한 것 (노트: `기록/계승노트/`)

| 노트 | 읽은 범위(전부 끝까지) | 설계자 검수 |
|---|---|---|
| `01_롱폼_학습로그.md`(1,090줄) | 롱폼 `study/bisa-learning.md` · `bisa-logs/learn_A~F`(1,865줄) · `frames-1008.md` · `origin-session-1008.md` · `shorts-notes-index-1008.md` · `web-research-1008.md` · `templates/README·_batch2·_batch3·카탈로그(857줄)` | 핵심 요약·bisa-learning·learn_A(분양4 세로)·origin-session·쇼츠 색인·웹조사 절을 직접 읽음 |
| `02_쇼츠광고_스터디A.md`(1,121줄) | 쇼츠 `study/` koba 강의 2·Maestro·newtake·claude-motion-graphics·higgsfield·flova·astra·dynamic·entry-reel·typography-remotion·README | 숏폼 표시 전부 + entry-reel 절을 원본 motion-typo 요약과 대조 |
| `03_쇼츠광고_스터디B_병행.md`(1,688줄) | 쇼츠 `study/` typo-ad 6·typo-pop 6·sfx-pop 8·sfx-theory · `기록/` BGM조사·타이포후보·3안 대본 · **병행작업** README·작업기록·레퍼해부·대본6·정책자금조사 · 소재 출처·라이선스 · 효과음 점검 txt 2 | 큰 그림 + 병행작업 전 절을 직접 읽음 |
| `04_영상제작_길라잡이.md`(869줄) | 영상제작 길라잡이 대본 5·신규2 소재조사·시장조사 5편 전사·레퍼런스6/8·모션그래픽·레퍼런스쇼츠·카피·광고주피드백·클라이언트요청·분양4 효과음 출처·분양과오2·숏폼자료 3·프리미어 편집분석·배경음악·예능효과음 5 · 빡이사DB 3 · ○○님 강의편집 9 · 파트너센터 · 도구 README · 예능스킬 5 | 대본 v4·v5·시장조사 5편·레퍼런스쇼츠 절 직접 읽음 |
| `05_영상제작_원본차이.md`(419줄) | 영상제작 `효과음-브랜드홍보-원칙` · `후킹애펙-워크플로우` · `AI영상-주의사항` · `진행기록` · `효과음` · `제작-자료` · `작업기록-0923` · `제작-레퍼런스` · `이어하기` · `도구/README` — 두 스킬로 **옮겨지지 않은 것만** 대조 추출 | 전부 직접 읽음 · 표본 2건 원문 대조(Kling 시작프레임 비율·자막 줄바꿈) 일치 |

에이전트 노트는 사실 추출만 했고 판단·규칙화는 설계자가 했다. 노트끼리·원본끼리 어긋난 것은 아래 3장.

## 2. 무엇을 어디에 옮겼나

| 가져온 것 | 출처 | 이 저장소 |
|---|---|---|
| 한 편 흐름 단계·확인 두 곳·편 유형 | 쇼츠 workflow(P0~P7·T1~T4) · 롱폼 auto-pipeline(①~⑨) · 분양4 장면 뼈대 · 병행작업 운영 | `workflow.md` |
| 모드 B(무인·아침 검수·유료 0) | 롱폼 auto-pipeline 7·8·15장 · bisa-learning 무인 사고 | `workflow.md` 5장 |
| 템플릿 서랍·매니페스트·도형 흉내 차단·느낌 | 롱폼 auto-pipeline 3·5장 · templates/README · tones | `drawers.md` · `templates/README.md` |
| 상황 강령·갈래 용어 사전 | 롱폼 situation-playbook · bisa-learning 5장 · 3안 피드백 | `situation-playbook.md` |
| 검증된 구조·훅·쉬운 말·금지 표현 | 병행작업(레퍼1·한비즈레퍼·대본6·정책자금 주의 11) · 분양 광고주 3차·시장 5편·v3/v4/v5 · 롱폼 web-research | `structure-playbook.md` |
| 세로 수치·재서 채울 칸 | 쇼츠 SKILL 6장 · editing-premiere 5·7장 · 분양 실측 · 시장 5편 · 레퍼1 · J-7 | `vertical-spec.md` |
| 연출 규칙·영상미·타이포 강령·반려 | 쇼츠 motion-typo J · motion-graphics 6·8·9장 · design-paths · 롱폼 motion-graphics 4장 · 원본차이(인코딩·마젠타 키) | `visual-rules.md` |
| 자막 | 쇼츠 editing-premiere 5-3·5-4·6·7·8장 · 원본차이(줄바꿈) | `captions.md` |
| 효과음·BGM·마감 | 쇼츠 sfx.md 전부 · 롱폼 sfx-workflow · 원본차이(장면음 레벨·스템) | `sfx.md` |
| AI 생성 | AI영상-주의사항 · 쇼츠 ai-video · 원본차이(Kling 비율) · learn_A(단가·207크레딧) | `ai-video.md` |
| 점검표 | 쇼츠 checklist A·B·C · 롱폼 checklist A~G · 3안 5-7~5-18 | `checklist.md` |
| 사장님 원문 | 세션 발언 전량 + 세 feedback-log | `feedback-log.md` |
| 재개 훅 | 영상제작·쇼츠·롱폼 `resume_guide.py` | `tools/resume_guide.py`(새로 씀) |
| 레퍼런스 해부 도구 | 쇼츠 `tools/ref_study.py` | `tools/ref_study.py`(사본) |

## 3. 원본끼리 어긋난 것 — 이 저장소의 결정

| 어긋남 | 결정 | 이유 |
|---|---|---|
| 납품: 분양4 «새 이름(v2·v3), 덮어쓰기 금지»(10-01) ↔ 쇼츠·롱폼 «같은 이름 제자리 덮어쓰기»(10-08~) ↔ 병행작업 «개편사항은 v2로»(10-12) | **고친 판은 같은 이름 덮어쓰기, 내용 개편·새 판 요청은 새 폴더 `_vN`**, 잠긴 파일은 남기고 알림 | 최신 두 지시(10-08 덮어쓰기 · 10-12 개편은 v2)를 둘 다 만족 |
| 효과음 기본 크기 −1/−2dB ↔ −2/−3dB(쇼츠 sfx.md 안에서도 337행 vs 174행) | −2/−3/−8(목소리 대비), 파일별 표가 우선 — 세로는 ☐ | 사장님 최종 완료본 역산값이 −2/−3 |
| 효과음 레벨 체계: 분양 v1~v4 전부 −24 LUFS ↔ LUFS 3단계 ↔ 목소리 대비 dB ↔ 음악 대비(10-12) | 형식별로 하나만(`sfx.md` 0·3장), 한 건에서 섞지 않는다 | 원본도 «섞지 않는다» |
| 효과음 밀도: 레퍼런스 «큰 순간 3~4번» ↔ 사장님 «2배정도 많이» | 한비즈 말 없는 타이포는 사장님 기준 | 사장님 말씀 > 레퍼런스 |
| HUD: 엔트리 릴·영상미 원칙 10 ↔ 10-12 «없애줘» | 금지 | 사장님 말씀 > 학습분 |
| PDF 자료: «잘라서 그대로 얹지 않는다»(제작-자료) ↔ «자료 구역만 오려 날것으로»(5차 반려 뒤) | 뒤의 것(오려서 크게, 푸터 제외) | 사장님 5차 지적이 나중 |
| 11번 장면 03:59 «흔들리는 연출 별로…»: 롱폼 learn_E «잘못 보낸 메시지» ↔ learn_F «반려 추정» | 세션 원문 확인 — 같은 시각 쇼츠광고 세션에 3안 1판 반려로 실제 보낸 말이고, 영상제작 세션엔 1분 뒤 «잘못보냈다». **3안(타이포) 반려로 읽는다** | 세션 발언 전량 대조 |
| «세로 레퍼런스가 레퍼1 한 편뿐»(노트 03) | 틀림 — 메타 광고 시장조사 5편(M01·M06·M07·M10·M16)도 전부 360×640 세로 | 노트 04 원문 |
| 84타입 세대수 1,753 ↔ 1,775(분양 자료 안) | 분양 고유 사실 — 이 저장소는 쓰지 않음 | 건 고유 |
| 예능 효과음 라이브러리 294개 ↔ 674개 ↔ 798건 | 최신 798건(쇼츠 등급표, 받은 677 + 사장님 121) | 시점 차이 |

## 4. 이 뼈대가 하지 않은 것

- 도구 대부분을 옮기지 않았다(`tools/README.md` 이식 후보 표) — 범위가 정해진 뒤 필요한 것만.
- 템플릿을 만들지 않았다(서랍 0개) — 계승 후보 목록만.
- 세로 수치를 채우지 않았다 — 재지 않은 값은 ☐.
- 원본 저장소의 미디어(효과음·글꼴·브랜드 로고)를 복사하지 않았다.
