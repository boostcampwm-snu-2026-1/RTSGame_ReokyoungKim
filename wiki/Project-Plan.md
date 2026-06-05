# RTSGame_ReokyoungKim — 프로젝트 기획서 (Project Plan)

> 자연어 프롬프트 → DB에서 유사 게임 시나리오 매칭 → 게임 config(JSON) 생성 → 브라우저 2D 플레이백 시각화
> Beyond All Reason(BAR, RTS 게임) 미니게임 생성기(minigame_generator_v4)의 **단순화판**

---

## 1. 서비스 주제 및 핵심 기능 정의

### 서비스가 무엇인가
RTSGame_ReokyoungKim은 사용자가 만들고 싶은 미니게임을 **한국어 자연어 한 문장으로 설명**하면, 기존에 검증된 시나리오 DB에서 가장 비슷한 시나리오를 찾아 BAR용 게임 설정(config JSON)을 자동 생성하고, 그 결과를 **브라우저에서 2D로 미리 보고 플레이백**할 수 있게 해 주는 도구다.

원본 `minigame_generator_v4`는 Designer / RuleDeveloper / ScriptDeveloper / Analyst 4개 에이전트가 LangGraph 피드백 루프와 BAR 게임엔진 시뮬레이터로 GDD를 새로 만들고 검증하는 multi-agent 구조였다. 본 프로젝트는 이를 **"GDD를 새로 생성하지 않고, DB에서 비슷한 시나리오를 찾아 script만 만드는"** 단일 흐름으로 단순화했다. rule도 새로 개발하지 않고 DB의 **기존 검증본(validated rule)** 만 사용한다. Designer GDD 생성, RuleDeveloper, Analyst 검증/리파인 루프, game_simulation(BAR 엔진)·psutil 의존성은 모두 제거되었다.

### 핵심 기능
1. **자연어 프롬프트 입력** — 사용자가 만들고 싶은 미니게임을 자유 텍스트로 설명한다. 예시 칩(중앙 기지 방어 / 시간 내 목표 건물 파괴 / 자원 제한 하 건설 버티기)으로 빠르게 시작할 수 있다.
2. **DB 시나리오 매칭** — `DBCall`이 LLM(gpt-5.2)으로 `db/scenario/meta.json`의 각 시나리오 설명을 프롬프트와 비교해 가장 비슷한 시나리오 한 개를 선택한다. 현재 DB에는 Fixed-Field Skirmish FFA / Team, Multi-Front Defense, Siege Planning, Time-Phased Production 5종이 있다.
3. **기존 시나리오 기반 GDD 구성** — 매칭된 시나리오의 `specification` 과 그 시나리오가 참조하는 **기존 검증 rule** 만 묶어 GDD 딕셔너리를 만든다(`load_existing_mode`). 새 rule 생성은 하지 않는다.
4. **Script(게임 config) 생성** — `ScriptDeveloperAgent`가 LangGraph 그래프로 `select_map → place_units → generate_rule_config → get_condition → assemble_draft` 5단계를 거쳐 최종 config JSON(`information`, `end_condition`, `unit_placement`, `customize`)을 조립한다.
5. **2D 시각화 (미니맵 + 플레이백)** — 생성된 `unit_placement`를 Canvas 2D 미니맵으로 그리고, 유닛 이동·교전·웨이브 스폰·승패 판정을 브라우저에서 근사 시뮬레이션해 재생/정지/리셋/속도(1×·4×·10×) 컨트롤로 플레이백한다.
6. **config 요약 및 내보내기** — 매칭 시나리오·맵·승패조건·팀별 유닛 수·gadget을 요약 카드로 보여 주고, 전체 config JSON을 복사하거나 파일로 다운로드할 수 있다.

---

## 2. 기술 스택 선택 및 선택 이유

### 백엔드 — Python + FastAPI
파이프라인 핵심 로직(LLM 호출, LangGraph 그래프, DB 매칭)이 모두 Python 생태계(LangGraph, LangChain, OpenAI SDK) 위에 있어 같은 언어로 묶는 것이 자연스럽다. FastAPI는 Pydantic 기반 요청 검증(`GenerateRequest`)과 비동기 처리, 가벼운 라우팅(`/generate`, `/catalog`, `/health`)을 적은 코드로 제공해 프로토타입 API 서버로 적합하다.

### 오케스트레이션 — LangGraph
`ScriptDeveloperAgent`의 script 생성은 맵 선택 → 유닛 배치 → rule config → 승패 조건 → 최종 조립이라는 **명확히 순서가 정해진 다단계 흐름**이다. LangGraph의 `StateGraph`로 각 단계를 노드로 정의하고 상태(`ScriptDeveloperState`)를 단계 간 전달하면, 단계별 로깅과 흐름 관리가 깔끔해진다. 원본의 analyst/verify 루프를 떼어 낸 뒤에도 단방향 그래프 구조를 그대로 재사용할 수 있다.

### LLM — OpenAI gpt-5.2
이 서비스의 두 가지 의미론적 판단(① 프롬프트와 DB 시나리오 설명의 유사도 매칭, ② 맵/유닛/조건의 자연어 추론)은 모두 LLM의 텍스트 이해에 의존한다. gpt-5.2를 단일 모델로 사용하고 `seed`를 받을 수 있게 해 재현성을 확보했다.

### 프론트엔드 — React + Vite
결과 화면이 요약·미니맵·플레이백·JSON 등 **상태를 공유하는 여러 컴포넌트**로 구성되므로 React의 컴포넌트/상태 모델이 잘 맞는다. Vite는 빠른 dev 서버와 `/api → http://localhost:8000` 프록시 설정으로 CORS 부담 없이 로컬에서 백엔드와 붙일 수 있어 개발 반복 속도가 빠르다. 의존성도 react/react-dom + @vitejs/plugin-react로 가볍게 유지했다.

### 시각화 — Canvas 2D
유닛 좌표를 점/사각형으로 그리고 매 프레임 위치·HP를 갱신하는 실시간 플레이백은 DOM 요소보다 Canvas 2D가 가볍고 빠르다. 별도 그래픽 라이브러리 없이 `requestAnimationFrame` 루프만으로 미니맵(MiniMap)과 시뮬레이션(SimPlayback)을 모두 그릴 수 있어 의존성을 최소화했다. 좌표계는 맵 size를 타일 단위로 받아 **1타일 = 512px** 로 환산한다.

---

## 3. 화면 흐름 및 페이지 구성 초안

### 사용자 플로우 (단계)
1. 페이지 진입 시 `GET /catalog`로 선택 가능한 시나리오·맵 목록을 미리 로드한다.
2. 사용자가 프롬프트를 입력하거나 예시 칩을 눌러 채운 뒤 **생성**(또는 ⌘/Ctrl+Enter)을 누른다.
3. 프론트가 `POST /generate { query, seed }`를 호출하고 "생성 중… (DB 매칭 → 스크립트 작성)" 로딩을 표시한다.
4. 백엔드 파이프라인이 3단계로 동작한다: (1) `find_scenario` DB 매칭 → (2) `load_existing_mode` GDD 구성 → (3) `ScriptDeveloperAgent.run` script 생성.
5. 응답 `{ scenario, config, raw }`를 받으면 결과 영역에 요약·미니맵·플레이백·JSON을 렌더링한다(config나 매칭이 없으면 에러 메시지 표시).
6. 사용자는 플레이백을 재생/정지/리셋/속도 조절하며 동작을 확인하고, 필요하면 config JSON을 복사하거나 다운로드한다.

### ASCII 플로우 다이어그램
```
[사용자]
   │  ① 프롬프트 입력 / 예시 칩 / 생성 클릭
   ▼
┌──────────────── Frontend (React + Vite) ────────────────┐
│  PromptInput ──▶ api.js: POST /api/generate {query,seed} │
│       ▲                         │  (Vite proxy /api→:8000)│
│       │                         ▼                         │
└───────┼─────────────────────────┼─────────────────────────┘
        │                         ▼
        │        ┌──────────── Backend (FastAPI) ───────────┐
        │        │  app.py: POST /generate                  │
        │        │     ▼                                     │
        │        │  pipeline.generate(query)                │
        │        │   (1) find_scenario  ── DBCall+LLM 매칭 ──┤──▶ db/scenario/meta.json
        │        │   (2) load_existing_mode ── 기존 rule ───┤──▶ db/rule/...
        │        │   (3) ScriptDeveloperAgent.run (LangGraph)│
        │        │        select_map → place_units →        │
        │        │        generate_rule_config →            │
        │        │        get_condition → assemble_draft     │
        │        │     ▼                                     │
        │        │  return {scenario, config, raw}          │
        │        └──────────────────┬────────────────────────┘
        │  ② 결과 렌더링            ▼
┌───────┴─────────────────────────────────────────────────┐
│  ConfigSummary │ MiniMap │ SimPlayback │ JsonView         │
└──────────────────────────────────────────────────────────┘
```

### 화면 / 컴포넌트 구성
단일 페이지(SPA, `App.jsx`) 위에 상단 입력부와 하단 결과부가 세로로 쌓이는 구성이다.

- **헤더** — 서비스 타이틀 "RTSGame Minigame Generator".
- **PromptInput** — 멀티라인 textarea + 예시 칩 3종 + 생성 버튼. ⌘/Ctrl+Enter 제출 지원, 로딩 중 비활성화.
- **결과 상단 (2열)**
  - **ConfigSummary** — 매칭된 시나리오(배지), 맵, 포맷/난이도, 전장의 안개 ON/OFF, 설명 리스트, 승리/패배 조건, 팀별 유닛 수, gadget(customize에 있을 때, "DB 기존 rule"로 표기) 요약.
  - **MiniMap** — `unit_placement`를 Canvas 2D 점으로 그리는 미니맵. 맵 size(타일×512)로 월드 크기를 잡거나, 없으면 유닛 좌표로 추정. 팀1(파랑)/팀2(빨강) 범례.
- **SimPlayback** — 브라우저 근사 플레이백 Canvas. 유닛 이동/최근접 교전/웨이브 스폰(`customize`의 스포너 gadget 감지)/승패 판정을 시뮬레이션하고, 재생·정지·리셋·속도(1×/4×/10×) 컨트롤과 시간·팀별 잔존 수 HUD, VICTORY/DEFEAT 배너를 표시. BAR 기준 ~30 FPS로 프레임→초 환산.
- **JsonView** — 전체 config JSON을 pre 영역에 출력, 복사·다운로드(시나리오명 기반 파일명) 버튼.

> 참고: 화면에는 난이도 선택 UI가 없으며, 백엔드가 `["normal"]` 단일 난이도 config만 생성·반환한다(`config = final_json.normal`).

---

### 저장소 / 협업 관리
- GitHub 저장소: `boostcampwm-snu-2026-1/RTSGame_ReokyoungKim`
- 브랜치 전략: `main` → `dev` → `feature/*` (feature별 작업 후 `feature → dev` PR)
- Task는 GitHub Issue로 관리, 기획/문서는 Wiki로 관리(본 문서 포함)

---

관련 파일 경로:
- 백엔드 파이프라인: /Users/reokyoungkim/Data/rtsgame/backend/pipeline.py
- API 서버: /Users/reokyoungkim/Data/rtsgame/backend/app.py
- Script 에이전트(LangGraph): /Users/reokyoungkim/Data/rtsgame/backend/script_builder.py
- DB 매칭: /Users/reokyoungkim/Data/rtsgame/backend/db_call.py
- 시나리오 DB 메타: /Users/reokyoungkim/Data/rtsgame/backend/db/scenario/meta.json
- 프론트 진입: /Users/reokyoungkim/Data/rtsgame/frontend/src/App.jsx
- 컴포넌트: /Users/reokyoungkim/Data/rtsgame/frontend/src/components/ (PromptInput, ConfigSummary, MiniMap, SimPlayback, JsonView)
- Vite 프록시 설정: /Users/reokyoungkim/Data/rtsgame/frontend/vite.config.js
