# 도구 — 지금 있는 것 · 이식 후보

원본 저장소는 **읽기 전용**이다. 옮길 때는 사본을 이 폴더에 두고 여기서 고친다(경로 상수는 `config.py` 한 곳으로). 새 렌더 도구는 점검기를 반드시 끼운다. 스크립트는 `_tmp/` 에 두지 않는다(재사용 = `tools/`, 장면 도구 = `tools/scenes/`).

## 지금 있는 것

| 파일 | 하는 일 | 출처 |
|---|---|---|
| `resume_guide.py` | SessionStart 훅 — SKILL 상시 규칙·멈추는 곳 + 작업기록 «지금 상태»«다음 작업 예정»을 대화에 넣음(6천 자 이하) | 이 저장소용으로 새로 씀(원형: 영상제작 `도구/점검/resume_guide.py`) |
| `channel_scan.py` | 쇼츠 채널 조사 — 키워드 검색으로 후보 수집(`search`) · 채널별 /shorts 최근 N개 조회수 중앙값·10만+ 비율·구독자(`measure`) | 이 저장소용(10-13) |
| `transcribe_words.py` | 롱폼 음성 → 단어 시각 전사(`words.json`·`transcript.md`). **기본 GPU large-v3**, 실패하면 CPU medium 자동 전환, `--offset` 으로 잘라 낸 음성 시각 보정 (`python tools/transcribe_words.py <음성.wav> <출력폴더> [--cpu] [--offset 초]`). 40분 음성: GPU 60초 시험 20.7초(로딩 포함) | 이 저장소용(10-13). 의존: faster-whisper · pip `nvidia-cublas-cu12`·`nvidia-cudnn-cu12==9.*`(10-13 설치, RTX 3050 6GB) |
| `s6_render.py` | **S6 롱폼 → 세로 쇼츠 조립기** — 편 계획 JSON → 1080×1920 30fps mp4 + SRT. 샷: face(하드컷 줌)·graphic(원본 영역 크게, overlays 실시간 들여오기·타자 칸)·pan(키프레임 팬, hold_until/hold_after, patch 가리기)·push(밀기 전환)·pip(작은 얼굴 원 확대)·card·typo(엔딩 CTA). 키프레임 확대 zoom·도구 연출 marks(상자·밑줄·동그라미) 모두 소수점 보간(잔흔들림 없음). 숨쉬기·드리프트는 폐기(10-13). 자막 A2 3프레임 페이드·전사 단어로 나눔 · 효과음 목소리 대비 rel · 음량 2회 맞춤 −14 LUFS·리미터 −2dB (`python tools/s6_render.py 기록/빡이사DB_계획/epNN.json [--preview 초]`) | 이 저장소용(10-13). 1분 편 렌더 약 1~2분 |
| `caption_fx.py` | **자막 + 글자 연출 층** — 연출계획 JSON(스티커·큰 숫자·계산식·라벨·화살표·▶▶·집중선·크기·색) → 층별 PNG + 프리미어 XML(V2~V5) + SRT + 미리보기(프레임 합성) | 이 저장소용(10-15) |
| `ref_caption.py` | **레퍼런스 쇼츠 똑같은 자막** — 받아쓰기(words.json) → 2~3어절 덩어리(DP, 어색한 자리 피함) → 강제 정렬 시각 → SRT + 프리미어 XML(V2 자막 그림) + 미리보기. 스타일 값은 머리말(레퍼런스 OVWZuG1KyV0 실측) | 이 저장소용(10-15) |
| `sfx_feel.py` | **효과음 결 재기** — 통과 효과음 6개와 소리 모양 거리(가까움/보통/멂). `sfx_pick.py` 정렬·점검 E4 가 씀. 캐시 `_tmp/sfx_feat.json` | 이 저장소용(10-15) |
| `scenes/board.py` | **S6 보드 장면** — 원본 요소 크게(img·live) + 큰 글자·칩·형광펜·상자·✓✕·커서를 원본 초(`at`)에 쌓기. 조립기 `board` 샷. 실화면 다시 그리기도 이것으로 | 이 저장소용(10-14 03·04 v2) |
| `scenes/locate.py` | **S6 위치 잡기 장면** — 무대 위 창에 실화면, 카메라 전체 → 칸(`cam` 원본 좌표), 표시 글자 경계 자동 정렬(`snap`)·라벨 정렬·창 끝 빈 줄 맞춤(`fit_edges`)·미니맵·단계 탭. 조립기 `locate` 샷, 어긋남은 렌더 로그 → 점검기 ERROR | 이 저장소용(10-15 03 v4) |
| `scenes/locate_demo.py` | 위치 잡기 5초 무음 시안(`_무대시안/위치잡기_시안.mp4`) | 이 저장소용(10-15) |
| `scenes/cta_typo.py` | **엔딩 CTA 타이포·모션 장면**(사람 없이, 편 내용에 맞춤) — comment_qa · next_ep · industry_chips · order_checklist. 조립기 `typo` 샷 + `at_typo` 효과음 | 이 저장소용(10-13) |
| `scenes/cta_board.py` | 엔딩 CTA 정지 시안 6장 비교판 | 이 저장소용(10-13) |
| `s6_check.py` | **S6 점검기**(사장님 10-13 «이런거 검사하는 검사장치») — 잇는 곳 말 끊김·숨 없이 붙음·컷 직후 원본 전환 잔상·튀는 프레임·자막 인지 텀·효과음 겹침/반복·말끝 잘림·엔딩 카드·LUFS/TP · **10-14 추가: D2 자막 싱크(완성본 강제 정렬 ↔ 첫 음절) · E3 한 편 같은 효과음 3회↑ · K 자료 잘림(위·아래 끝이 글자·카드·사진을 가름) · N 업체명·번호 OCR(easyocr)** — 셋 다 ERROR. `--no-ocr` 로 N 생략. ERROR 0 이어야 납품 (`python tools/s6_check.py <계획.json>`) | 이 저장소용(10-13) |
| `align_chars.py` | **대본 글자 ↔ 목소리 강제 정렬**(CTC, kresnik/wav2vec2-large-xlsr-korean · HF 캐시 · 음절 1,205개, 숫자·영문은 [UNK]) → 음절마다 시각(20ms). 자막 시각의 정본. 의존: `transformers`(10-14 설치) · torchaudio | 이 저장소용(10-14) |
| `caption_sync.py` | 계획 자막 ↔ 목소리 싱크 재기·맞추기(10-14 «자막이랑 목소리 나오는 타이밍 정확도»). 조각마다 강제 정렬 → 자막 첫 음절 시각. 전사 단어 시각·음량 쉼은 경계를 0.3~0.6초 틀려서 안 씀. 숫자로 시작하는 자막은 정렬이 흔들려 옮기지 않음. `--fix` 는 그 시각에 묶인 확대·표시·효과음 키도 같이 옮김 (`python tools/caption_sync.py <계획.json> [--fix]`) | 이 저장소용(10-14) |
| `name_mask.py` | 원본 화면 OCR(0.1초, 화면이 그대로면 건너뜀) → 실제 업체명·전화번호 자리에 시간대별 가림 상자(`mask`)를 계획에 넣음 (`python tools/name_mask.py <계획.json>`). 로고·그림 속 이름은 못 봄 → 눈으로 한 번 더 | 이 저장소용(10-14) |
| `sfx_overlay.py` | **완성 영상에 효과음·장면음·BGM 얹기** — 큐 JSON(sfx 타격 · beds 장면음 from~to · bgm 곡 끝 맞춤) → 영상 스트림 복사 + 오디오만 새로. 고역 셸빙·순간음 페이드인 다듬기·짧은 울림 버스·BGM EQ(50Hz·2.5k·9k)·목소리 대비 −13dB + 쉼에서 올라옴. 들리는 시작/정점 맞춤(휙 정점 앞 0.35초 상한)·자연 길이 2.5초·겹치면 앞 소리 끊기·같은 파일 3회/3초 반복 WARN·−14 LUFS·TP −1.5 (`python tools/sfx_overlay.py <큐.json>`) | 이 저장소용(10-19 ○○역) |
| `sfx_pick.py` | 효과음 후보 — 역할(확대·표시·확정·허수·메시지·반짝·코믹·놀람·귀여움…)별 라이브러리 분류(`D:\영상제작\소재\예능효과음`, 674개·라이선스 기록)에서 **이 편에 덜 쓴 파일**부터 (`python tools/sfx_pick.py <역할> --plan <계획.json>`). 마림바·실로폰 제외. 등급표는 경로가 옛 PC 기준이라 안 씀 | 이 저장소용(10-14) |
| `export_public.py` | **직원 공유 공개본 만들기** — 허용 목록만 `_tmp/public/` 으로 복사 · 사람 이름·현장·영업 구조 가림 · 피드백 로그는 빈 틀 · 하네스(~/.claude) 사본 · 큐 예시 · **민감어가 남으면 실패**(`python tools/export_public.py`) | 이 저장소용(10-29) |
| `burned_caption_times.py` | 롱폼에 구운 자막이 바뀌는 순간을 프레임 차이로 잼 → 자막 정본의 시각 | 이 저장소용(10-13) |
| `ref_study.py` | 레퍼런스 영상 해부 — 접촉 시트·전사·컷·움직임·소리 타격·박자 맞춤 → `<폴더>/study/` (`python tools/ref_study.py _tmp/study/<영상ID> [--long] [--from 초] [--to 초]`) | 쇼츠광고 `tools/ref_study.py` 사본(10-13). 의존: numpy·Pillow·ffmpeg·(전사) faster-whisper·(박자) librosa |

## 이식 후보 — 범위가 정해지면 필요한 것만 (☐)

**쇼츠광고 `C:\Users\user\Desktop\한비즈-쇼츠광고\tools\`** (세로 1080×1920 기준으로 만든 것)
| 파일 | 하는 일 | 상태(원본 기준) |
|---|---|---|
| `config.py` | 경로·규격 한 곳(AE·효과음·글꼴·크롬·W,H,FPS, 환경변수로 덮어쓰기) | 쓰는 중 |
| `edit_plan.py` · `edit_render.py` · `edit_xml.py` · `edit_smoke.py` | **한 편 조립기** — 배치표 JSON 스키마·검증·사장님 초안 읽기 / 미리보기 mp4 + 점검 / 프리미어 XML + `media/` + 다시 조립 대조 | 합성 소재 시험 통과, 프리미어 열기 미확인 |
| `html_motion.py` (+ `scenes/html/*.html`) | HTML `seek(t)` 장면 → 크롬 캡처 → 모션블러 → ProRes 4444 알파 · 렌더 전 겹침·인지 텀·3색 점검 · EVENTS → 효과음 큐 | 3안 1~11판에 씀 |
| `sfx.py` · `sfx_check.py` · `sfx_audit.py` · `sfx_make_counter.py` · `sfx_make_reverse.py` · `sfx_synth_mallet.py`(마림바 금지 이후 쓰지 않음) · `sfx_ref*.py` · `sfx_mixkit_crawl.py` | 효과음 고르기·다듬기·크기 / 새 소재 검사 / 밀림·겹침 점검 / 카운터 굴림 소리 / 역재생 / 레퍼런스 소리 분석 / Mixkit 받기 | 쓰는 중 |
| `scenes/hanbiz_ad_sfx_preview.py` | 효과음 큐 → BGM + 효과음 미리듣기(음악 대비 크기 맞춤·겹침 끊기·들리는 시각 맞춤) | 3안에 씀 |
| `bgm_analyze.py` · `bgm_build_table.py` · `bgm_mixkit_crawl.py` | BGM 후보 BPM·LUFS·대역 분석·후보표 | 10-12 |
| `rule_check.py` | 점검기 `check_plan`·`check_sfx`(3-튜플)·`check_tone`·`report` | 쓰는 중 |
| `ae_scene.py` · `rf3_ae.py` · `design_layers.py` | AE 조각·겹침 검사·감시 실행·JSX 공용 함수 / 클로드 디자인 레이어 | 쓰는 중 |
| `read_prproj.py` · `prproj_timeline.py` · `words.py` · `lec_xml.py` | 프리미어 읽기(0dB = 0.17783) · 단어 시각(faster-whisper CPU int8 medium + 말 시작 당기기) · «얹을 것만» XML | 쓰는 중 |
| `scenes/hanbiz_logo_*.py` · `scenes/subtitle_style_compare.py` | 로고 엔딩 3종(효과음 포함) · 자막 시안 | 10-08 완성·시안 |
| `data/예능효과음-등급.json` · `예능효과음-실사용.json` | 효과음 등급표 798건 · 통과/반려 | 쓰는 중 |

**롱폼자동화 `C:\Users\user\Desktop\한비즈-롱폼자동화\tools\`**
| 파일 | 하는 일 |
|---|---|
| `auto/registry.py` | 템플릿 매니페스트 검사(도형 흉내·태그·출처) → registry.json·카탈로그.md |
| `glyph_check.py` | 글꼴에 없는 글자 렌더 전 점검 |
| `session_digest.py` | 세션 jsonl → 사람 말·답만 md |
| `corner_name_scan.py` | 완성본 왼쪽 위(상호·계정 자리) OCR → 가릴 시간대 목록만 |
| `sfx_find.py` | 효과음 폴더 지도·뜻별 단골·이름 찾기 |
| `transcribe_words.py` · `read_lecture_edit.py` · `cut_*` · `pause_compress.py` | S6(롱폼 → 쇼츠)를 맡게 되면: 단어 시각 · prproj 전수 읽기 · 무음 컷 |

**영상제작 `D:\영상제작\도구\`** (분양 세로 장면 도구 — 템플릿 승격 후보의 원본, `drawers.md` 4장 A): `광고편집/b4_*.py` · `ae_double/comm/school/money/stamp.py` · `rf3_render.py`·`rf3_pages.py` · `sg_*.py`(자막 단어 시각 정렬·XML 다시 조립 대조) · `v5_render.py`(프리미어 없이 파이썬 프레임 합성) · `rs_render.py` · `ns_render.py` · `소리/pa_voice.py`(Windows 내장 음성 역 스피커 가공) · `소리/seq1_align.py`(STT 없이 대본 정렬) · `읽기/gfx_text.py`(프리미어 텍스트 그래픽 글자 해독) · `레퍼런스분석/mg_study.py`.
