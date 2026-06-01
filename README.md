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
├── backend/                    # Python: 단일 에이전트 + API
│   ├── app.py                  # FastAPI: POST /generate, GET /catalog
│   ├── generator.py            # 단일 LLM 호출 → config JSON
│   ├── schema.py               # config 출력 스키마 / 검증
│   ├── data/                   # v4의 info/*.json 에서 정제 복사
│   │   ├── maps.json
│   │   ├── units.json
│   │   └── gadgets.json
│   ├── requirements.txt
│   └── .env.example
└── frontend/                   # React + Vite
    ├── src/
    │   ├── App.jsx             # 메인: 입력 + 결과 레이아웃
    │   ├── api.js              # backend 호출 클라이언트
    │   ├── components/
    │   │   ├── PromptInput.jsx     # 프롬프트 입력 + 생성 버튼
    │   │   ├── ConfigSummary.jsx   # 설명/승패조건/유닛 요약 카드
    │   │   ├── MiniMap.jsx         # unit_placement 2D 시각화
    │   │   └── JsonView.jsx        # raw config JSON + 다운로드
    │   └── main.jsx
    ├── index.html
    ├── package.json
    └── vite.config.js
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

## 구현 Plan

### 1단계 — 백엔드 단일 에이전트 (`backend/generator.py`)
- 하나의 시스템 프롬프트에 맵/유닛/gadget 카탈로그 + 출력 JSON 스키마를 주입.
- `generate(prompt) → config JSON` 단일 LLM 호출 (structured output).
- LangGraph · 피드백 루프 · DB · visualize_logs(96KB) · game_simulator 전부 제거.
- OpenAI 클라이언트는 v4 `agents/common.py`의 `get_client` 패턴 재사용.

### 2단계 — 데이터 정제 (`backend/data/`)
- `info/map.json` → `maps.json` (거의 그대로 활용).
- `info/units_info.json` + `armada_units.json` → `units.json` (이름·역할·비용 등 핵심 필드만 추림).
- `info/gadget.json` → `gadgets.json` (사용 가능한 gadget + 파라미터 스펙).

### 3단계 — API 서버 (`backend/app.py`)
- `POST /generate {prompt}` → 생성된 config JSON 반환.
- `GET /catalog` → 프론트 드롭다운용 맵/유닛 목록.
- CORS 허용 (Vite dev 서버용).

### 4단계 — 프론트엔드 (`frontend/`)
- Vite React 스캐폴드.
- **PromptInput**: 텍스트 입력 + "생성" 버튼 + 로딩 상태.
- **ConfigSummary**: 게임 설명, 맵, 승리/패배 조건, 유닛 수 요약.
- **JsonView**: raw config 표시 + JSON 다운로드.
- **MiniMap**: 맵 크기 비례 캔버스에 팀별 유닛 좌표 점 찍기 — 결과를 직관적으로 확인.

### 5단계 — 문서
- 백엔드/프론트 실행법, `.env` 설정(OPENAI_API_KEY), 아키텍처 설명 보강.

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

## 미확정 결정

- **LLM 모델**: v4는 `gpt-5.2` 사용 중 — 유지할지 변경할지.
- **난이도 분기**: easy/normal/hard 3종 생성 유지 vs 단일 config만 생성.
- **MiniMap 시각화**: 1차 범위 포함(추천) vs 후순위.

> 기본값 제안: **gpt-5.2 유지 / 단일 config / MiniMap 포함**.
