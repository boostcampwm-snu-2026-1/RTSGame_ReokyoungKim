"""
Simplified pipeline: DB match -> script.

    user query
      -> (1) find the most similar scenario in db/scenario   (DBCall, LLM match)
      -> (2) build a gdd from that existing scenario          (load_existing_mode)
      -> (3) generate the final script                        (ScriptDeveloperAgent)

No new GDD generation, no rule development (existing validated rules only),
no analyst / verify loop.
"""

import os
import re
import json
import shutil
import datetime
from pathlib import Path
from dotenv import load_dotenv

from db_call import DBCall
from script_builder import ScriptDeveloperAgent

load_dotenv()

CURRENT_DIR = Path(__file__).resolve().parent
DB_DIR = CURRENT_DIR / "db"


# --------------------------------------------------------------------------- #
# (1) Find the most similar existing scenario in the DB
# --------------------------------------------------------------------------- #
def find_scenario(query: str, seed: int = None) -> str:
    """Return the best-matching scenario name from db/scenario, or None."""
    db = DBCall(seed=seed)
    _, names = db.call_with_names(query, folder="scenario")
    if not names:
        print("   ⚠️ No matching scenario found in DB.")
        return None
    print(f"   🔎 Matched scenario(s): {names} -> using '{names[0]}'")
    return names[0]


# --------------------------------------------------------------------------- #
# (2) Build a gdd from an existing DB scenario (existing rules only)
# --------------------------------------------------------------------------- #
def _normalize_name(name: str) -> str:
    name = re.sub(r'\s*\(.*?\)\s*', '', name)
    name = name.lower().strip()
    name = re.sub(r'[-_ ]+', '_', name)
    return name


def _resolve_db_name(llm_name: str, candidates: list) -> str:
    if not llm_name or not candidates:
        return llm_name
    if llm_name in candidates:
        return llm_name
    norm = _normalize_name(llm_name)
    for key in candidates:
        if _normalize_name(key) == norm:
            return key
    for key in candidates:
        nk = _normalize_name(key)
        if nk in norm or norm in nk:
            return key
    return llm_name


def load_existing_mode(gdd_name: str, session_timestamp: str) -> dict:
    """Load an existing scenario from db/scenario and build a gdd dict using
    only existing, validated rules referenced by the scenario."""
    scenario_meta_path = DB_DIR / "scenario" / "meta.json"
    try:
        with open(scenario_meta_path, "r", encoding="utf-8") as f:
            scenario_meta = json.load(f)
    except Exception as e:
        print(f"   ⚠️ Failed to load scenario meta: {e}")
        return {}

    details = scenario_meta.get("details", {})
    if gdd_name not in details:
        resolved = _resolve_db_name(gdd_name, list(details.keys()))
        if resolved != gdd_name and resolved in details:
            print(f"   🔗 Fuzzy-matched '{gdd_name}' -> '{resolved}'")
            gdd_name = resolved
        else:
            print(f"   ⚠️ Scenario '{gdd_name}' not found in DB.")
            return {}

    scenario_path = DB_DIR / details[gdd_name].get("file", "")
    try:
        with open(scenario_path, "r", encoding="utf-8") as f:
            scenario_data = json.load(f)
    except Exception as e:
        print(f"   ⚠️ Failed to load scenario file: {e}")
        return {}

    rules_temp = CURRENT_DIR / "log" / session_timestamp / "developer" / "rules_temp"
    os.makedirs(rules_temp, exist_ok=True)
    db_codes_dir = DB_DIR / "rule" / "codes"

    rules = []
    for rule_ref in scenario_data.get("rule", []):
        rule_path = DB_DIR / rule_ref
        try:
            with open(rule_path, "r", encoding="utf-8") as f:
                rule_data = json.load(f)
            code_info = rule_data.get("code", {})
            rule_name = code_info.get("name", "")
            rules.append({
                "action": "existing",
                "name": rule_name,
                "logic_description": code_info.get("description", ""),
                "config_format": code_info.get("config_format", {}),
                "config_example": code_info.get("config_example", {}),
                "validated": True
            })
            src_lua = db_codes_dir / f"{rule_name}.lua"
            dst_lua = rules_temp / f"{rule_name}.lua"
            if src_lua.exists() and not dst_lua.exists():
                shutil.copy2(str(src_lua), str(dst_lua))
        except Exception as e:
            print(f"   ⚠️ Failed to load rule {rule_ref}: {e}")

    gdd = {
        "gdd": gdd_name,
        "game_description": scenario_data.get("specification", ""),
        "decision": scenario_data.get("decision", []),
        "rules": rules,
        "reasoning": f"Loaded existing mode '{gdd_name}' from DB.",
        "assessing_ability": ""
    }
    print(f"   📦 Loaded existing mode: {gdd_name} ({len(rules)} existing rule(s))")
    return gdd


# --------------------------------------------------------------------------- #
# (3) + orchestration
# --------------------------------------------------------------------------- #
def generate(query: str, seed: int = None) -> dict:
    """Run the full simplified pipeline and return:
        {
          "scenario": <matched scenario name>,
          "config": <the generated scenario config>,   # normal difficulty
          "raw": <full developer result>
        }
    """
    session_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*60}\n  SIMPLIFIED PIPELINE (DB match -> script)\n  Query: {query}\n{'='*60}")

    print("\n[1/3] Searching DB for a similar scenario...")
    scenario_name = find_scenario(query, seed=seed)
    if not scenario_name:
        return {"error": "no_matching_scenario", "config": None}

    print("\n[2/3] Building gdd from existing scenario...")
    gdd = load_existing_mode(scenario_name, session_timestamp)
    if not gdd:
        return {"error": "failed_to_load_scenario", "config": None}

    print("\n[3/3] Generating script from gdd...")
    developer = ScriptDeveloperAgent(session_timestamp=session_timestamp, seed=seed)
    result = developer.run(user_intent=query, gdd=gdd)

    final_json = result.get("final_json", {}) or {}
    # difficulties default to ["normal"]; take the first available config.
    config = None
    if final_json:
        config = final_json.get("normal") or next(iter(final_json.values()), None)

    return {"scenario": scenario_name, "config": config, "raw": result}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print('Usage: python pipeline.py "<game mode description>"')
        sys.exit(1)
    out = generate(sys.argv[1])
    print("\n" + "=" * 60 + "\n  RESULT\n" + "=" * 60)
    print(json.dumps(out.get("config"), ensure_ascii=False, indent=2))
