# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Text prompt → Beyond All Reason (BAR) minigame config (JSON) generator. A natural-language
query is matched against a database of existing game scenarios, then a final scenario config is
synthesized and visualized in the browser. The README is in Korean and is the canonical design doc.

## Commands

Backend (FastAPI, Python 3.11):
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env            # set OPENAI_API_KEY (BASE_URL optional)
uvicorn app:app --reload        # http://localhost:8000
python pipeline.py "<prompt>"   # run the full pipeline from the CLI, no server
python db_call.py               # smoke-test DB folder/file LLM routing
```

Frontend (React + Vite, requires Node 20):
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api -> :8000
npm run build                   # production build (this is what CI runs)
```

There is no test suite. CI (`.github/workflows/ci.yml`, on push/PR to `main`/`dev`) only does
`npm run build` for the frontend and, for the backend, `python -m compileall` + `import app`
with a dummy `OPENAI_API_KEY`. **Module import must stay side-effect-free** (no LLM client built
at import time) or CI breaks — clients are constructed lazily inside functions/constructors.

## Architecture

The core design decision: **do not generate a GDD or new rules from scratch.** Find the most
similar existing scenario in `backend/db/`, reuse its validated rules, and only synthesize the
final script. An earlier multi-agent build with an analyst/verify loop was deliberately stripped
to remove the `game_simulation` (BAR engine) and `psutil` runtime dependencies — do not
reintroduce them.

### Backend pipeline (`backend/pipeline.py`, `generate()`) — 3 steps

1. **`find_scenario(query)`** — match the prompt to a scenario in `db/scenario/meta.json`.
   Resilient by design: LLM match (`DBCall`) → keyword overlap fallback (`_keyword_fallback`) →
   default to the first scenario. Returns `None` only if the scenario DB is unreadable.
2. **`load_existing_mode(name)`** — build a `gdd` dict from the scenario's `specification` and its
   referenced rules. Every rule is loaded as `action: existing, validated: True` (never generated).
   Rule `.lua` files are copied into the per-session `log/<timestamp>/.../rules_temp/`.
3. **`ScriptDeveloperAgent.run()`** (`script_builder.py`) — a linear LangGraph:
   `select_map → place_units → generate_rule_config → get_condition → assemble_draft`. Each node
   is one LLM call (prompts in `developer_prompt.py`); `select_map`/`place_units` loop, issuing
   `call_db` actions to fetch more context, until the LLM returns `finish`.

`generate()` returns `{scenario, config, raw}` where `config` is the `"normal"` difficulty entry of
`final_json`. The agent always produces exactly the `["normal"]` difficulty.

### DBCall (`backend/db_call.py`) — two-stage LLM retrieval

`db/meta.json` lists folders (`scenario`, `map`, `unit`, `rule`, `decision`, `verify`, `rubric`);
each folder's `meta.json` has a `details` map of `{name: {description, file}}`. `DBCall.call(query)`
asks the LLM to pick a folder, then which files within it — returning file paths relative to `db/`.
Pass `folder=` to skip folder selection. `call_with_names()` also returns the matched DB key names
(used by `find_scenario`).

### API (`backend/app.py`)

- `POST /generate {query, seed?}` → pipeline result. `seed` is threaded down to every `ChatOpenAI`
  for reproducibility.
- `GET /catalog` → scenarios (from `db/scenario/meta.json`) + maps (from `info/map.json`).
- `GET /health`. CORS is wide open (`*`).
- The top-level `try/except` returns `{error, config: None}` rather than raising.

### Frontend (`frontend/src/`)

`App.jsx` loads `/catalog` on mount and calls `/generate` via `api.js`. Components: `PromptInput`
(prompt + example chips, ⌘/Ctrl+Enter to submit), `ConfigSummary`, `MiniMap` (2D canvas of
`unit_placement`), `SimPlayback`, `JsonView`. No state library, no router.

## Key conventions

- **LLM model** is hardcoded to `gpt-5.2` in `common.get_client()`. Reads `OPENAI_API_KEY` and
  optional `BASE_URL` from env. All token usage flows through the shared `TokenTracker` callback.
- **Coordinate system:** maps are sized in tiles where **1 tile = 512px**. A 16×16 map → 8192×8192
  pixels. Units are placed in pixel coordinates. Prompts and `MiniMap` both rely on this.
- **Config shape** (`assemble_draft` output): `{information, end_condition, unit_placement, customize}`.
  `unit_placement` is keyed by team (`"1"`, `"2"`) → list of `[unit_code, [x, y]]`. `customize` holds
  rule/gadget config (e.g. `enemy_wave_spawner`).
- **`backend/db/`** is the source of truth (scenarios, validated rules + their `.lua` codes, maps,
  units, decisions). **`backend/info/`** holds flat unit/map/gadget summaries fed into prompts
  (`units_info.json`, `map.json`, etc.) — distinct from `db/`.
- **Logs:** every pipeline run writes to `backend/log/<timestamp>/` (gitignored). Each agent node
  dumps its raw result via `common.log_node_result`.
- **Name matching is fuzzy on purpose:** `pipeline._resolve_db_name` / `_normalize_name` reconcile
  LLM-returned names against DB keys (case, spaces, parentheses, hyphens). Keep this when LLM output
  may not match DB keys exactly.

## Git workflow

`main → dev → feature/*`. Branch `feature/*` off `dev`; PR `feature/* → dev`; release via
`dev → main`. PRs close issues with `Closes #<n>`. Project docs live in the GitHub Wiki (`wiki/`).
