"""
FastAPI server for the simplified RTS minigame generator.

Endpoints:
    GET  /health    -> liveness check
    GET  /catalog   -> available scenarios + maps (for the frontend)
    POST /generate  -> { "query": "..." } -> generated game config
"""

import json
import os
import sys
import subprocess
from pathlib import Path

# Windows consoles default to cp949 in a Korean locale; the pipeline's progress
# logs contain emoji (🔎, ⚠️, …). Without this, the first such print() raises
# UnicodeEncodeError and bubbles up as a /generate failure. Force UTF-8 so logs
# never crash a request.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import pipeline

CURRENT_DIR = Path(__file__).resolve().parent
DB_DIR = CURRENT_DIR / "db"
INFO_DIR = CURRENT_DIR / "info"
RULE_CODES_DIR = DB_DIR / "rule" / "codes"

# The full BAR launcher lives in the bundled v4 project. Its game_simulator
# converts a config (same JSON shape this backend emits) into a Spring start
# script and launches spring.exe. It reads its own .env (SPRING_DATADIR,
# BAR_ENGINE_PATH, GAME_VERSION) via load_dotenv inside main.py.
V4_DIR = CURRENT_DIR.parent / "minigame_generator_v4"
SIM_DIR = V4_DIR / "game_simulator"
SIM_MAIN = SIM_DIR / "main.py"

app = FastAPI(title="RTSGame Minigame Generator", version="0.1.0")

# Allow the Vite dev server (and others) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# A deployed HTTPS page (e.g. the Vercel site) calling this local backend at
# http://localhost:8000 triggers Chrome's Private Network Access check, which
# needs this header on the preflight response. Added after CORS so it wraps the
# CORS preflight reply. Harmless on the cloud backend (header just unused).
@app.middleware("http")
async def allow_private_network(request, call_next):
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


class GenerateRequest(BaseModel):
    query: str
    seed: int | None = None


def _load_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalog")
def catalog():
    """Return the scenario and map catalog so the frontend can show what the
    DB-matching step can choose from."""
    scenario_meta = _load_json(DB_DIR / "scenario" / "meta.json", {})
    scenarios = [
        {"name": name, "description": info.get("description", "")}
        for name, info in scenario_meta.get("details", {}).items()
    ]

    map_info = _load_json(INFO_DIR / "map.json", {})
    maps = [
        {"name": name, "size": info.get("size"), "description": info.get("description", "")}
        for name, info in map_info.items()
    ]

    return {"scenarios": scenarios, "maps": maps}


@app.post("/generate")
def generate(req: GenerateRequest):
    """Run the simplified pipeline: DB scenario match -> script."""
    try:
        result = pipeline.generate(req.query, seed=req.seed)
        return result
    except Exception as e:
        return {"error": str(e), "config": None}


class LaunchRequest(BaseModel):
    config: dict
    # "gadget" = run the scenario's own gadgets only (no movement/vlm AI);
    # "movement"/"vlm" enable the v4 experiment gadgets.
    mode: str = "gadget"


def _resolve_gadgets(config: dict) -> list:
    """Each customize key corresponds to a rule gadget whose Lua lives at
    db/rule/codes/<key>.lua. The launcher copies these into the engine and
    enables them; the per-key config is delivered via the scenariooptions blob.
    Missing files are skipped (the scenario still launches without them)."""
    gadgets = []
    for key in (config.get("customize") or {}):
        lua = RULE_CODES_DIR / f"{key}.lua"
        if lua.exists():
            gadgets.append(str(lua))
    return gadgets


@app.post("/launch")
def launch(req: LaunchRequest):
    """Launch the generated config in the actual BAR client via the bundled
    v4 game_simulator. Fire-and-forget: spring.exe opens its own window and the
    request returns as soon as the process is spawned."""
    if not SIM_MAIN.exists():
        return {"launched": False, "error": f"BAR launcher not found at {SIM_MAIN}"}

    config = req.config or {}
    if not config.get("information", {}).get("map_name"):
        return {"launched": False, "error": "config has no information.map_name"}

    # Prefer the v4 venv interpreter — it has the deps (PIL/numpy/dotenv) that
    # game_simulator/utils import; fall back to whatever `python` is on PATH.
    venv_py = V4_DIR / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_py) if venv_py.exists() else "python"

    gen_dir = SIM_DIR / "_generated"
    gen_dir.mkdir(exist_ok=True)
    cfg_path = gen_dir / "launch_config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    gadgets = _resolve_gadgets(config)

    cmd = [python_exe, str(SIM_MAIN), "--config", str(cfg_path), "--mode", req.mode]
    if gadgets:
        cmd += ["--gadgets"] + gadgets

    log_dir = CURRENT_DIR / "log"
    log_dir.mkdir(exist_ok=True)
    try:
        log_fh = open(log_dir / "launch.log", "a", encoding="utf-8")
        # New process group so the game survives a uvicorn reload/restart.
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        subprocess.Popen(
            cmd, cwd=str(SIM_DIR),
            stdout=log_fh, stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    except Exception as e:
        return {"launched": False, "error": str(e)}

    return {
        "launched": True,
        "mode": req.mode,
        "map": config["information"]["map_name"],
        "gadgets": [Path(g).stem for g in gadgets],
    }


# Serve the built frontend if present, so `start_local` can run the whole app
# (UI + API + BAR launch) as a single Python process — no Node needed at run
# time. On the cloud backend dist isn't deployed, so this is skipped and the API
# runs alone (the frontend is hosted separately on Vercel). Mounted LAST so the
# API routes above always take precedence.
_DIST = CURRENT_DIR.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
