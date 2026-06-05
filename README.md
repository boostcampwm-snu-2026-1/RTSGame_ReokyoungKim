# rtsgame — BAR Minigame Generator (Simplified)

`minigame_generator_v4`의 multi-agent 파이프라인을 **단일 LLM 에이전트**로 축소하고,
**React + Vite** 프론트엔드(프롬프트 입력 + 결과 보기)를 붙인 독립 프로젝트.

텍스트 프롬프트 → Beyond All Reason(BAR) 미니게임 config(JSON) 생성.

---

## 아키텍처

```
┌─────────────────┐    POST /generate     ┌──────────────────────┐
│  React + Vite   │ ───────────────────►  │   FastAPI backend    │
│   (frontend)    │ ◄─────────────────── │  단일 LLM 에이전트    │
│ 프롬프트 입력    │     config JSON       │  generator.py        │
│ 결과/시각화 보기 │    GET /catalog       │  + data 카탈로그      │
└─────────────────┘                       └──────────────────────┘
```

> 프론트는 React+Vite이지만 생성 로직이 Python이라, 둘을 잇는 얇은 FastAPI 백엔드를 둔다.
> (기존 `front_end`의 backend/frontend 분리 패턴과 동일)

---

## 폴더 구조

```
rtsgame/
├── README.md
├── backend/                    # Python: 단순화 파이프라인 + API
│   ├── app.py                  # FastAPI: POST /generate, GET /catalog, GET /health
│   ├── pipeline.py             # ① DB 매칭 → ② gdd 구성 → ③ script 생성 오케스트레이션
│   ├── script_builder.py       # ScriptDeveloper (analyst/verify 제거한 경량 그래프)
│   ├── db_call.py              # DBCall: scenario LLM 매칭
│   ├── common.py               # LLM 클라이언트 + DB 로더
│   ├── developer_prompt.py     # 맵선택/유닛배치/rule/조건 프롬프트
│   ├── db/                     # 시나리오·rule·map·unit·decision DB (v4에서 복사)
│   ├── info/                   # 유닛/맵 정보 (units_info.json 등)
│   ├── requirements.txt
│   └── .env.example
└── frontend/                   # React + Vite
    ├── index.html
    ├── package.json
    ├── vite.config.js          # /api → http://localhost:8000 프록시
    └── src/
        ├── main.jsx
        ├── App.jsx             # 입력 + 결과 레이아웃 + catalog 로딩
        ├── api.js              # backend 호출 (/api/generate, /api/catalog)
        ├── styles.css
        └── components/
            ├── PromptInput.jsx     # 프롬프트 입력 + 예시 칩 + 생성 버튼
            ├── ConfigSummary.jsx   # 매칭 시나리오/맵/승패조건/유닛/gadget 요약
            ├── MiniMap.jsx         # unit_placement 2D 캔버스 시각화
            └── JsonView.jsx        # config JSON + 복사/다운로드
```

---

## 생성 config 포맷

```jsonc
{
  "information": {
    "description": ["게임 설명 문장들..."],
    "match_format": "1v1",
    "map_name": "altored_divide_bar_remake_1.6.2",
    "fog_of_war": false
  },
  "end_condition": {
    "victory_condition": ["and", { "time": [">= 1200"] }],
    "defeat_condition": ["or",  { "1": ["armcom == 0"] }]
  },
  "unit_placement": {
    "1": [["armcom", [4096, 4096]], ["armlab", [4240, 4096]]],  // 팀1 유닛 + 픽셀 좌표
    "2": []                                                      // 팀2
  },
  "customize": {
    "enemy_wave_spawner": { "enabled": true, "waveIntervalFrames": 1800, ... }
  }
}
```

- 맵 size는 타일 단위(타일 = 512px). 예: 16×16 맵 → 8192×8192 픽셀.
- 유닛은 픽셀 좌표로 배치.

---

## 구현 방식 (✅ 구현 완료)

핵심: **GDD를 새로 생성하지 않고**, 기존 DB에서 비슷한 시나리오를 찾아 script만 만든다.
**rule(gadget)도 새로 만들지 않고 DB의 검증된 것만 사용**한다.

### 백엔드 파이프라인 (`backend/pipeline.py`) — 3 스텝
1. **`find_scenario(query)`** — `DBCall`이 `db/scenario/meta.json` 설명을 LLM으로 매칭해 가장 비슷한 시나리오 선택.
2. **`load_existing_mode(name)`** — 시나리오의 `specification` + 참조 rule로 gdd 구성. rule은 모두 `action: existing`, `validated: True` (기존 검증본).
3. **`ScriptDeveloperAgent.run()`** (`script_builder.py`) — 맵선택 → 유닛배치 → rule config → end_condition → 조립. **analyst/verify 루프 제거**로 `game_simulation`(BAR 엔진)·`psutil` 의존성을 런타임에서 완전히 들어냄.

### 제거된 것 (v4 대비 단순화)
- Designer의 **새 GDD 생성**·대화·intent 분석 전체
- **RuleDeveloper** 전체 (rule은 DB에서만)
- **Analyst** 검증/refine 루프 + 그것이 끌고오던 게임엔진 시뮬레이터 의존성
- agent_manager 오케스트레이션, visualize_logs

### API 서버 (`backend/app.py`)
- `POST /generate {query}` → `{ scenario, config, raw }` (config = 생성된 시나리오 JSON).
- `GET /catalog` → 매칭 가능한 시나리오 + 맵 목록 (프론트 표시용).
- `GET /health`, CORS 허용.

### 프론트엔드 (`frontend/`)
- **PromptInput**: 텍스트 입력 + 예시 칩 + 생성 버튼 (⌘/Ctrl+Enter).
- **ConfigSummary**: 매칭 시나리오, 맵, 승/패 조건, 팀별 유닛 수, gadget 요약.
- **MiniMap**: 맵 크기(타일×512px) 비례 캔버스에 팀별 유닛 좌표를 점으로 시각화.
- **JsonView**: config JSON 표시 + 복사/다운로드.

---

## 실행 방법 (예정)

```bash
# 백엔드
cd rtsgame/backend
pip install -r requirements.txt
cp .env.example .env          # OPENAI_API_KEY 입력
uvicorn app:app --reload      # http://localhost:8000

# 프론트엔드
cd rtsgame/frontend
npm install
npm run dev                   # http://localhost:5173
```

---

## 결정 사항

- **LLM 모델**: `gpt-5.2` 유지 (`common.get_client`).
- **난이도**: `normal` 단일 config 생성.
- **MiniMap 시각화**: 포함.
- **rule**: DB의 기존 검증된 rule만 사용 (새 rule 생성 안 함).

## 검증 상태

- ✅ 백엔드 import·그래프 빌드 검증 (analyst/game_simulation 의존성 런타임 제거 확인).
- ✅ 프론트엔드 `npm run build` 통과.
- ⚠️ **실제 LLM 생성은 아직 미실행** — `backend/.env`에 `OPENAI_API_KEY` 입력 후 한 번 돌려서 end-to-end 확인 필요.

---

## 프로젝트 정보

**한 줄 소개:** 자연어 프롬프트로 RTS 게임(Beyond All Reason) 미니게임 시나리오를 생성하는 도구입니다. 프롬프트를 입력하면 DB에서 가장 비슷한 게임 시나리오를 매칭하고, 게임 config(JSON)를 생성한 뒤, 브라우저에서 2D 플레이백으로 시각화합니다.

**저장소:** [boostcampwm-snu-2026-1/RTSGame_ReokyoungKim](https://github.com/boostcampwm-snu-2026-1/RTSGame_ReokyoungKim)

**주요 기술 스택:**

| 구분 | 기술 |
| --- | --- |
| 백엔드 | Python, FastAPI, LangGraph, OpenAI gpt-5.2 |
| 프론트엔드 | React, Vite, Canvas 2D |

**폴더 요약:**

| 폴더 | 설명 |
| --- | --- |
| `backend/` | Python + FastAPI 서버. 자연어 쿼리를 받아 시나리오 매칭 → gdd 구성 → script 생성의 3단계 파이프라인을 수행. 주요 모듈: `pipeline.py`, `script_builder.py`, `db_call.py`, `developer_prompt.py`, `db/`(scenario·rule·map·unit·decision 데이터) |
| `frontend/` | React + Vite SPA. 프롬프트 입력(`PromptInput`), 시나리오/맵/승패조건 요약(`ConfigSummary`), 2D 배치 미니맵(`MiniMap`), 브라우저 근사 플레이백(`SimPlayback`), config JSON 뷰어(`JsonView`) 컴포넌트로 구성. `/api`는 `localhost:8000`으로 프록시 |

---

## 개발 관리

### 브랜치 전략

`main → dev → feature/*` 3단계 브랜치 전략을 사용합니다.

| 브랜치 | 역할 |
| --- | --- |
| `main` | 릴리스(배포) 브랜치. 항상 동작이 보장되는 안정 버전만 유지합니다. |
| `dev` | 통합(개발) 브랜치. 완료된 기능들을 모아 검증하는 기본 작업 브랜치입니다. |
| `feature/*` | 기능 단위 작업 브랜치. 이슈(Task) 하나당 하나의 `feature/*` 브랜치에서 개발합니다. |

```text
feature/find-scenario ─┐
feature/sim-playback  ─┼─▶ dev ─────▶ main
feature/mini-map      ─┘  (통합/검증)   (릴리스)
```

- `feature/*`는 항상 `dev`에서 분기하여 작업합니다.
- 작업이 끝나면 `feature/* → dev`로 PR을 올려 병합합니다.
- `dev`에서 검증이 끝난 안정 버전을 `dev → main`으로 병합하여 릴리스합니다.

### 이슈 관리

모든 작업(Task)은 **GitHub Issues**로 등록하고 관리합니다.

- 하나의 이슈는 하나의 작업 단위(기능/버그/문서 등)를 의미하며, 이슈 단위로 `feature/*` 브랜치를 생성합니다.
- PR에는 관련 이슈 번호를 연결(`Closes #번호`)하여 병합 시 자동으로 이슈가 닫히도록 합니다.

**라벨 규칙:**

| 라벨 | 용도 |
| --- | --- |
| `feature` | 신규 기능 개발 |
| `bug` | 버그 수정 |
| `docs` | 문서 작업 |
| `enhancement` | 기존 기능 개선 |
| `backend` | 백엔드(FastAPI/파이프라인) 관련 |
| `frontend` | 프론트엔드(React/시각화) 관련 |

### 문서 관리

프로젝트 문서는 **GitHub Wiki**에서 관리합니다.

- **기획서:** 프로젝트 목표, 단순화 배경(원본 multi-agent 구조 → 단일 흐름), config(JSON) 구조 및 좌표계(1타일 = 512px) 등 설계 정보를 정리합니다.
- **Agent 개발 workflow:** `ScriptDeveloperAgent`의 LangGraph 그래프 흐름(`select_map → place_units → generate_rule_config → get_condition → assemble_draft`)과 DB(scenario·rule·map·unit) 활용 방식을 문서화합니다.

### PR 흐름

1. **feature → dev PR:** 기능 개발이 완료되면 `feature/*`에서 `dev`로 PR을 생성합니다.
   - PR 제목/본문에 작업 내용과 관련 이슈 번호를 명시합니다.
   - 최소 1인 이상의 **코드 리뷰 승인** 후에만 병합합니다.
   - 병합 방식은 커밋 이력을 정리하기 위해 **Squash and merge**를 기본으로 합니다.
2. **리뷰/머지 규칙:** 리뷰어는 동작 검증과 코드 컨벤션을 확인하고, 변경 요청(Request changes) 사항이 해결되면 승인합니다. 병합 후 `feature/*` 브랜치는 삭제합니다.
3. **dev → main 릴리스:** `dev`에 누적된 기능이 검증되면 `dev → main`으로 PR을 생성하여 릴리스합니다. 릴리스 시점에는 버전 태그를 부여하여 배포 단위를 관리합니다.
