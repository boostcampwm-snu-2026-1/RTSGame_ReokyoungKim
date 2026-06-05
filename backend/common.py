import json, base64
import os
import threading
from typing import List, Optional, TypedDict, Dict, Any, Annotated, Union

from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from pathlib import Path


class TokenTracker(BaseCallbackHandler):
    """Accumulates input/output token counts across all LLM calls."""

    def __init__(self):
        self._lock = threading.Lock()
        self.input_tokens = 0
        self.output_tokens = 0

    def on_llm_end(self, response, **kwargs):
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg is None:
                    continue
                usage = getattr(msg, "usage_metadata", None)
                if usage:
                    with self._lock:
                        self.input_tokens += usage.get("input_tokens", 0)
                        self.output_tokens += usage.get("output_tokens", 0)

    def get_usage(self) -> dict:
        with self._lock:
            return {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            }

    def reset(self):
        with self._lock:
            self.input_tokens = 0
            self.output_tokens = 0


_token_tracker = TokenTracker()


def get_token_usage() -> dict:
    return _token_tracker.get_usage()


def reset_token_usage():
    _token_tracker.reset()


def get_client(seed: int = None):
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BASE_URL")
    if not api_key: raise ValueError("API_KEY is missing in .env")
    kwargs = {"model": "gpt-5.2", "api_key": api_key, "base_url": base_url, "callbacks": [_token_tracker]}
    if seed is not None:
        kwargs["seed"] = seed
    return ChatOpenAI(**kwargs)

def load_gdds_as_str(gdd_path: str) -> str:
        try:
            with open(gdd_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                summary = []
                for mode in data:
                    name = mode.get('gdd', 'Unknown')
                    desc = mode.get('game_description', '')
                    summary.append(f"- {name}: {desc}")
                return "\n".join(summary)
        except:
            return "No pre-defined GDDs available."
    
def find_mode_from_json(file_path: str, target_mode_name: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for item in data:
            if item.get("gdd") == target_mode_name:
                return item       
        return None

    except FileNotFoundError:
        print(" Cannot find file.")
        return None

def load_info(file_path: str) -> dict:
    file = os.path.join(file_path)
    data = {}
    try:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[System Error] File not found at path: {file_path}")
    return data

def load_map_info(file: str) -> str:
    file_path = os.path.join(file)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        formatted_lines = []
        
        for map_name, details in data.items():
            
            terrains = ", ".join(details['terrain_types'].values())
            description_text = f"Size: {details['size']}, Terrains: [{terrains}], Description: [{details['description']}]"
            
            line = f"- Map name: {map_name} | Desc: {description_text}"
            
            formatted_lines.append(line)

        final_text = "\n".join(formatted_lines)
    except FileNotFoundError:
            final_text = f"[System Error] File not found at path: {file_path}"
    return final_text

def get_terrain_info(map_filename: str, folder: str):
        base_name = os.path.basename(map_filename)
        name_without_ext = os.path.splitext(base_name)[0]
        
        target_filename = f"{name_without_ext}_analysis.json"
        target_path = os.path.join(folder, target_filename)

        print(f"[System] Looking for map analysis at: {target_path}")

        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                    print("[System] Analysis data loaded successfully.")
                    strategic_map = { item["sector_id"]: item for item in raw_list }
                    return strategic_map
            
            except Exception as e:
                print(f"[Error] Failed to read analysis file: {e}")
                return "{}" 
        else:
            print(f"[Warning] Analysis file not found. Using empty data.")
            return "{}"

def load_unit_summary(file: str) -> str:
        file_path = os.path.join(file)
        if not os.path.exists(file_path):
            return f"[System Error] File not found at path: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return f"[System Error] Failed to decode JSON. Check file syntax: {file_path}"
        except Exception as e:
            return f"[System Error] Unexpected error loading file: {e}"

        if not isinstance(data, dict):
            return "[System Error] JSON root must be a dictionary (Key-Value pairs)."

        category_definitions = {
            "Bot": "All-terrain infantry. capable of climbing steep hills where vehicles cannot go. Generally slower but versatile.",
            "Vehicle": "Fast heavy units. High speed and HP but restricted to flat terrain. Cannot climb steep cliffs.",
            "Ship": "Naval units. Restricted to Deep Water. High HP and Range.",
            "Hover": "Amphibious units. Can travel on both Water and Land. Fast but cannot climb hills.",
            "Air": "Flying units. Ignores terrain constraints. Very fast but generally fragile.",
            "Seaplane": "Amphibious aircraft. Can land/repair on water.",
            "Spider": "All-terrain walkers. Can climb ANY surface including vertical cliffs.",
        }

        summary_lines = []
        
        for category, units in data.items():
            summary_lines.append(f"### Category: {category}")
            
            cat_desc = category_definitions.get(category, "General unit group.")
            summary_lines.append(f"> **Overview:** {cat_desc}\n")

            if not isinstance(units, dict):
                continue

            for unit_name, details in units.items():
                code = details.get("code", "UNKNOWN_ID")
                tech = details.get("Tech", "N/A")
                desc = details.get("Explanation", "No description.")

                line = f"- **{unit_name}** (`{code}` | {tech}): {desc}"
                summary_lines.append(line)
            
            summary_lines.append("") 

        return "\n".join(summary_lines).strip()

def load_prompt(prompt_path: str) -> str:
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read()
    return prompt

def log_node_result(step_name: str, data: str, timestamp: str, log_dir: str):
    filename = f"{step_name}_{timestamp}.json"
    file_path = os.path.join(log_dir, filename)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"[Logger] Saved {step_name} result to {file_path}")
    except Exception as e:
            print(f"[Logger Error] Failed to save {step_name}: {e}")

def load_from_db(file_paths: list) -> str:
    current_dir = Path(__file__).resolve().parent
    db_path = current_dir / "db"
    combined_results = []
    for file in file_paths:
        target_file = db_path / file
        try:
            if target_file.exists():
                with open(target_file, "r", encoding="utf-8") as f:
                    if target_file.suffix == ".lua":
                        content = f.read()
                        entry = f"[\nFile: {file}\nContent:\n{content}\n]\n"
                    else:
                        data = json.load(f)
                        json_str = json.dumps(data, indent=2, ensure_ascii=False)
                        entry = f"[\nFile: {file}\nContent:\n{json_str}\n]\n"
                    combined_results.append(entry)
            else:
                print(f"⚠️ File not found: {target_file}")

        except Exception as e:
            print(f"❌ Error reading {file}: {e}")

    return "\n".join(combined_results)


def load_json_from_db(file_paths: list) -> List[Union[Dict, List]]:
    current_dir = Path(__file__).resolve().parent
    db_path = current_dir / "db"
    
    combined_results = [] 
    
    for file in file_paths:
        target_file = db_path / file
        try:
            if target_file.exists():
                with open(target_file, "r", encoding="utf-8") as f:
                    data = json.load(f) 

                    combined_results.append(data)
            else:
                print(f"⚠️ File not found: {target_file}")

        except Exception as e:
            print(f"❌ Error reading {file}: {e}")

    return combined_results
        
def compare(a, op, b):
    if op == "==": return a == b
    if op == "!=": return a != b
    if op == ">": return a > b
    if op == ">=": return a >= b
    if op == "<": return a < b
    if op == "<=": return a <= b
    return False

def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')