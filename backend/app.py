"""
FastAPI server for the simplified RTS minigame generator.

Endpoints:
    GET  /health    -> liveness check
    GET  /catalog   -> available scenarios + maps (for the frontend)
    POST /generate  -> { "query": "..." } -> generated game config
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pipeline

CURRENT_DIR = Path(__file__).resolve().parent
DB_DIR = CURRENT_DIR / "db"
INFO_DIR = CURRENT_DIR / "info"

app = FastAPI(title="RTSGame Minigame Generator", version="0.1.0")

# Allow the Vite dev server (and others) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
