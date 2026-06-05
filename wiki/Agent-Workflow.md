# Agent 개발 Workflow 흐름 초안

> 대상 프로젝트: **RTSGame_ReokyoungKim** — Beyond All Reason(BAR) 미니게임 생성기의 단순화판
> 한 줄 요약: 자연어 프롬프트 → DB에서 비슷한 게임 시나리오 매칭 → 게임 config(JSON) 생성 → 브라우저 2D 플레이백 시각화
> 저장소: `boostcampwm-snu-2026-1/RTSGame_ReokyoungKim` · 브랜치 전략: `main → dev → feature/*`

이 문서는 Claude Code 같은 AI 에이전트(**Agent Skill + MD 파일**)를 사용해 개발을 굴리는 방식을 정리한 초안이다. 사람이 "무엇을/어떤 맥락으로" 지시하고 "무엇을 반드시 검증"하는지에 초점을 둔다.

---

## 1. 개발 Workflow 개요

AI 에이전트는 코드를 빠르게 생성하지만, **작업 정의 / 맥락 제공 / 검증**은 사람이 책임진다. 이 프로젝트는 GitHub Issue를 작업 단위로, Wiki를 기획/규칙 저장소로, `CLAUDE.md` + Agent Skill을 에이전트의 상시 컨텍스트로 사용한다.

### 1.1 한 사이클 흐름도

```
┌──────────────┐
│  ① Issue 생성 │  Task를 GitHub Issue로 등록 (배경/완료조건/영향 모듈 명시)
└──────┬───────┘
       │
┌──────▼───────┐
│ ② 브랜치 분기 │  dev에서 feature/<issue#>-<요약> 분기
└──────┬───────┘
       │
┌──────▼─────────────┐
│ ③ AI에 작업 요청     │  CLAUDE.md + Wiki 규칙 + 프롬프트 템플릿(§3)으로 컨텍스트 주입
│   (Agent Skill/MD)  │  → 에이전트가 코드/config 생성·수정
└──────┬─────────────┘
       │
┌──────▼───────┐
│ ④ 검증        │  사람이 §4 체크리스트로 확인
│              │  - backend: uvicorn 기동 + /health + /generate 스모크
│              │  - frontend: npm run build + 브라우저 플레이백 확인
│              │  - 생성 config JSON 스키마/좌표 유효성
└──────┬───────┘
       │  실패 시 → ③로 (구체적 피드백과 함께 재요청)
       │
┌──────▼───────┐
│ ⑤ PR 생성     │  feature → dev PR. 변경 요약/검증 결과/스크린샷 첨부
└──────┬───────┘
       │
┌──────▼───────┐
│ ⑥ 리뷰·머지   │  /code-review 또는 사람 리뷰 → dev 머지 → 주기적으로 dev → main
└──────────────┘
```

### 1.2 각 단계에서 사람 vs AI 역할

| 단계 | 사람(나) | AI 에이전트 |
|---|---|---|
| ① Issue | 작업 정의, 완료 조건, 영향 모듈 지정 | (선택) Issue 초안 작성 보조 |
| ② 브랜치 | 브랜치 네이밍 결정 | 브랜치 생성 명령 실행 |
| ③ 작업 요청 | 맥락·제약 주입, 범위 한정 | 코드/config 생성·수정 |
| ④ 검증 | **최종 판단(§4)** | 빌드/테스트 실행, 로그 요약 |
| ⑤ PR | 변경 요약 검수 | PR 본문 초안, diff 요약 |
| ⑥ 리뷰 | 머지 승인 | 자동 리뷰 코멘트 |

### 1.3 에이전트 상시 컨텍스트 자산

- **`CLAUDE.md`**: 저장소 구조, 실행 명령, 환경변수 위치, 코딩 규칙. 에이전트가 매 작업에서 자동 참조.
- **GitHub Wiki**: 게임 config 스키마, 좌표계(1타일=512px), 시나리오/rule DB 규칙 등 도메인 지식.
- **Agent Skill**: 반복 작업(예: "새 컴포넌트 스캐폴딩", "엔드포인트 스모크 테스트")을 절차화해 재사용.

---

## 2. 작업 단위 쪼개기 기준

핵심 원칙: **하나의 PR은 하나의 검증 가능한 단위**여야 한다. 백엔드 파이프라인 한 step과 그에 대응하는 프론트 표시를 무작정 한 PR에 묶지 않는다.

### 2.1 기능 단위(Feature) vs 컴포넌트 단위(Component)

| 기준 | 기능 단위로 쪼갬 | 컴포넌트 단위로 쪼갬 |
|---|---|---|
| 정의 | end-to-end 사용자 가치 1개 (예: "fog_of_war 토글 지원") | 코드 구조상 1개 모듈/컴포넌트 (예: `MiniMap`) |
| 언제 | 새 동작이 backend+frontend를 모두 건드릴 때 | 한쪽 레이어 안에서 독립적으로 변경 가능할 때 |
| PR 크기 | 중~대 (수직 슬라이스) | 소 (수평, 단일 파일/모듈 중심) |
| 예 | "유닛 customize(gadget) 파라미터 노출" | "`SimPlayback` 속도 조절 UI만 추가" |

**판단 플로우**:
1. 이 작업이 **API 계약(`POST /generate` 응답 형태)**을 바꾸나? → Yes면 backend 먼저 독립 PR로 쪼개고, frontend는 후속 PR.
2. 한 레이어 안에서 끝나나? → 컴포넌트/모듈 단위 단일 PR.
3. 둘 다 건드리지만 계약은 그대로인가? → 기능 단위 수직 슬라이스 1 PR 허용.

### 2.2 이 프로젝트 기준 구체 예시

**예시 A — 기능 단위로 쪼개야 하는 경우: "맵 선택을 사용자가 강제 지정"**
- `feature/12-backend-map-override`: `pipeline.find_scenario` / `load_existing_mode`에 map override 인자 추가, `/generate` 요청 스키마에 `map_name?` 추가 → **API 계약 변경이므로 단독 PR**
- `feature/13-frontend-map-picker`: `PromptInput`에 맵 선택 드롭다운(`GET /catalog`의 `maps` 사용) → 위 PR 머지 후 진행

**예시 B — 컴포넌트 단위로 충분한 경우: "MiniMap에 팀별 색상 범례 추가"**
- `feature/20-minimap-legend`: `MiniMap.jsx` 캔버스 렌더링만 변경. backend·계약 무관 → **단일 소형 PR**

**예시 C — 백엔드 파이프라인 step 단위: "ScriptDeveloper 그래프에 노드 추가"**
- LangGraph 그래프(`select_map → place_units → generate_rule_config → get_condition → assemble_draft`)는 노드별로 쪼갠다.
- 예: `feature/31-script-balance-pass`: `assemble_draft` 직전 밸런스 점검 노드 1개 추가. `script_builder.py` + `developer_prompt.py`만 수정, 출력 config 스키마는 불변 유지 → 회귀 위험 최소화.

### 2.3 쪼개기 안티패턴 (피할 것)

- ❌ "scenario DB 추가 + rule DB 추가 + 프론트 카탈로그 UI"를 한 PR에 — 검증 표면이 너무 넓다.
- ❌ config 스키마 변경과 무관한 리팩터링을 기능 PR에 섞기 — diff 노이즈로 리뷰 약화.
- ✅ DB 데이터 추가(`db/scenario/*`, `db/rule/*`)는 코드 변경과 분리해 별도 PR로.

---

## 3. AI 요청 프롬프트 패턴 초안

공통 원칙: **(맥락) → (작업) → (제약/불변식) → (검증 방법)** 순서로 준다. 특히 "건드리지 말 것"과 "이 계약은 유지"를 명시하는 것이 회귀를 막는 핵심이다.

### 패턴 1 — 새 프론트엔드 컴포넌트 추가

```text
[맥락]
- 프로젝트: RTSGame_ReokyoungKim, frontend는 React + Vite (rtsgame/frontend).
- 기존 컴포넌트: PromptInput, ConfigSummary, MiniMap, SimPlayback, JsonView.
- 데이터 소스: POST /generate 응답의 { scenario, config, raw }. config 구조는
  information / end_condition / unit_placement / customize. 좌표계 1타일=512px.
- api 호출은 src/api.js를 통해서만. dev 프록시 /api -> :8000.

[작업]
- 새 컴포넌트 <컴포넌트명>.jsx 추가: <한 줄 목적>.
- 입력 props: <명시>. config의 <필드>만 읽는다.

[제약]
- 기존 컴포넌트 파일·props 시그니처를 바꾸지 말 것.
- 새 API/엔드포인트 추가 금지. 새 npm 의존성 추가 금지(불가피하면 먼저 물어볼 것).
- 스타일은 기존 컴포넌트 컨벤션을 따른다.

[검증]
- npm run build 통과해야 함.
- 끝나면 변경 파일 목록 + 통합 위치(App.jsx 어디에 mount했는지) 보고.
```

### 패턴 2 — 백엔드 엔드포인트/파이프라인 변경

```text
[맥락]
- backend: Python + FastAPI (rtsgame/backend). 핵심: pipeline.py 3-step
  (find_scenario -> load_existing_mode -> ScriptDeveloperAgent.run).
- 현재 API: POST /generate {query} -> {scenario, config, raw} / GET /catalog / GET /health.
- 원칙: GDD 새 생성 없음, rule은 db/rule의 검증본만 사용, analyst/verify 루프 없음.

[작업]
- <엔드포인트 또는 pipeline step> 변경: <목적>.
- 입출력 스키마: <요청/응답 필드 명시>.

[제약]
- /generate 응답 최상위 키 (scenario, config, raw)는 유지 — 변경 시 먼저 알릴 것.
- config 스키마(information/end_condition/unit_placement/customize) 깨지 않기.
- 제거된 의존성(game_simulation, psutil, BAR 엔진) 다시 들이지 말 것.
- LLM 모델은 gpt-5.2 고정. 새 외부 호출 추가 시 명시.

[검증]
- uvicorn 기동 후: GET /health, 그리고 POST /generate 샘플 query 1건 스모크 결과 보여줄 것.
- 응답 config를 JSON으로 출력해 스키마 일치 확인.
```

### 패턴 3 — 버그 수정

```text
[맥락]
- 증상: <재현 절차와 기대 vs 실제>.
- 관련 영역: <backend pipeline.py / frontend SimPlayback 등 추정 위치>.
- 관련 데이터: 사용한 query, 반환된 config(JSON) 첨부.

[작업]
- 근본 원인을 먼저 진단해 한 줄로 설명한 뒤 최소 수정.
- 추측 수정 금지: 원인을 못 찾으면 멈추고 추가 로그/정보를 요청할 것.

[제약]
- 수정 범위는 버그에 한정. 무관한 리팩터링·포맷 변경 금지.
- 공개 API 계약과 config 스키마 불변.

[검증]
- 재현 절차로 수정 전/후 동작 차이를 보여줄 것.
- backend면 /generate 스모크, frontend면 npm run build + 해당 화면 동작 확인.
```

---

## 4. 직접 검증/판단해야 할 체크포인트

AI가 끝났다고 한 작업은 **머지 전에 사람이 아래를 반드시 확인**한다. 항목별로 "왜"를 함께 둔다.

### 4.1 보안 / 키 노출
- [ ] OpenAI API 키 등 시크릿이 코드/커밋/로그에 하드코딩되지 않았는가. (`.env`만 사용, `.gitignore` 포함 확인)
- [ ] `git diff`에 `.env`, 자격증명, 내부 경로가 섞이지 않았는가.
- [ ] LLM 프롬프트에 불필요한 민감 정보를 넣고 있지 않은가.

### 4.2 API 계약 일치
- [ ] `POST /generate` 응답 최상위 키 `{scenario, config, raw}`가 유지되는가.
- [ ] frontend `src/api.js`가 기대하는 필드와 backend 실제 응답이 일치하는가. (계약 드리프트 = 런타임 깨짐)
- [ ] `GET /catalog`의 `{scenarios, maps}` 형태가 `PromptInput` 예시칩/선택 UI와 맞는가.

### 4.3 빌드 / 기동 통과
- [ ] backend: `uvicorn` 기동 성공 + `GET /health` 200.
- [ ] frontend: `npm run build` 무경고 통과 + `npm run dev`로 화면 정상 렌더.
- [ ] 제거됐어야 할 의존성(game_simulation, psutil, BAR 엔진)이 다시 import되지 않았는가.

### 4.4 생성 config 유효성
- [ ] 필수 블록 존재: `information`, `end_condition`, `unit_placement`, `customize`.
- [ ] `end_condition`에 `victory_condition` / `defeat_condition`이 모두 있는가.
- [ ] `unit_placement` 좌표가 맵 size(타일 × 512px) 범위 안인가 — 음수/범위 초과 좌표 없는가.
- [ ] `unitcode`가 실제 unit DB에 존재하는 코드인가. `map_name`이 `db/map`에 있는가.
- [ ] rule이 DB의 기존 검증본에서만 왔는가(새로 지어낸 rule 아님).
- [ ] 생성 config로 `SimPlayback`이 실제로 재생되고 승패 판정이 나는가(유닛 이동/교전/웨이브).

### 4.5 비용 / LLM 호출
- [ ] `/generate` 1회당 LLM 호출 수가 의도대로인가(불필요한 중복 호출/루프 없는가 — analyst/verify 루프는 제거된 상태 유지).
- [ ] 모델이 `gpt-5.2`로 고정돼 있고, 더 비싼 모델로 바뀌지 않았는가.
- [ ] 프롬프트에 전체 DB를 통째로 싣는 등 토큰 낭비가 없는가(meta.json 설명 매칭만 사용).

### 4.6 회귀 / 범위
- [ ] 요청 범위 밖 파일이 변경되지 않았는가(무관한 리팩터링 혼입 여부).
- [ ] LangGraph 그래프 노드 순서(`select_map → place_units → generate_rule_config → get_condition → assemble_draft`)가 의도대로 유지/변경됐는가.
- [ ] 브랜치 방향이 맞는가(`feature/* → dev` PR, `main` 직접 푸시 아님).

---

> 이 문서는 **초안**이다. 실제 운영하며 프롬프트 템플릿(§3)과 체크리스트(§4)를 Wiki에서 계속 업데이트한다.
