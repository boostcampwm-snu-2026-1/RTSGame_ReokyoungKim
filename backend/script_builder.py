import json, os, datetime, re
from typing import List, Optional, TypedDict, Dict, Any, Annotated
import numpy as np
from glob import glob
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from collections import Counter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from dotenv import load_dotenv
from pathlib import Path
from developer_prompt import SELECT_MAP_PROMPT, PLACE_UNITS_PROMPT, RULE_CONFIG_PROMPT, GET_CONDITION_PROMPT, REFINE_SCRIPT_PROMPT
from db_call import DBCall

import common

load_dotenv()

class ScriptDeveloperState(TypedDict):
    user_intent: str
    gdd: Dict[str, Any]
    selected_map: Dict     
    unit_config: Dict[str, Dict[str, Any]]  
    rule_config: Dict[str, Dict[str, Any]]
    end_config: Dict[str, Dict[str, Any]]    
    final_json: Dict    

    is_script_valid: bool
    script_feedback: str
    loop_count: int
    refined_diffs: list



class ScriptDeveloperAgent:
    def __init__(self, session_timestamp, seed: int = None):
        self.current_dir = Path(__file__).resolve().parent
        INFO_PATH = self.current_dir / "info"

        self.unit_summary = common.load_unit_summary(INFO_PATH / "units_info.json")

        self.session_timestamp = session_timestamp
        self.log_dir = self.current_dir / "log" / session_timestamp / "developer"
        os.makedirs(self.log_dir, exist_ok=True)

        # Feedback log for tracking all feedback
        self.feedback_log_path = self.log_dir / f"script_feedback_{session_timestamp}.json"
        self.feedback_logs = []

        # Reasoning log for tracking design decisions
        self.reasoning_logs = []

        self.client = common.get_client(seed=seed)
        self.parser = JsonOutputParser()
        self.db_caller = DBCall(seed=seed)
        # NOTE: Analyst and the verify/refine loop are intentionally dropped in
        # this simplified build (removes the game_simulation/psutil dependency).

        builder = StateGraph(ScriptDeveloperState)

        builder.add_node("select_map", self.select_map)
        builder.add_node("place_units", self.place_units)
        builder.add_node("generate_rule_config", self.generate_rule_config)
        builder.add_node("get_condition", self.get_condition)
        builder.add_node("assemble_draft", self.assemble_draft)

        builder.add_edge(START, "select_map")
        builder.add_edge("select_map", "place_units")
        builder.add_edge("place_units", "generate_rule_config")
        builder.add_edge("generate_rule_config", "get_condition")
        builder.add_edge("get_condition", "assemble_draft")
        builder.add_edge("assemble_draft", END)

        self.graph = builder.compile()
    
    def select_map(self, state: ScriptDeveloperState) -> ScriptDeveloperState:
        user_intent = state.get("user_intent", "")
        gdd = state.get("gdd", {})
        current_map_list = []
        
        print("\n[Developer] 1. Selecting Map...")
        for _ in range(3):
            prompt = ChatPromptTemplate.from_messages([
                ("system", SELECT_MAP_PROMPT),
                ("user", """

                [User intent]
                {user_intent}
                
                [GDD]
                {gdd}
                
                [Available Map List]
                {map_list}
                Select the best map.
                """)
            ])
            
            chain = prompt | self.client | self.parser
            
            result = chain.invoke({
                "user_intent": user_intent,
                "gdd": json.dumps(gdd, ensure_ascii=False),
                "map_list": current_map_list
            })
            action = result.get("action")
                
            if action == "call_db":
                query = f"Find maps matching the query: {result.get('query')}"
                print(f"[Map Selector] Searching DB for: '{query}'")
                
                found_paths = self.db_caller.call(query)
                
                new_maps_str = common.load_from_db(found_paths)
                
                if new_maps_str:
                    print(f" Found maps. Updating context...")
                    if isinstance(new_maps_str, list):
                        current_map_list.extend(new_maps_str)
                    else:
                        current_map_list.append(new_maps_str)
                else:
                    print("No maps found in DB. Asking LLM to pick from whatever creates.")
        
            elif action == "finish":
                selected_map = result.get("selected_map", {})
                reason = result.get("reason", "")
                print(f"Selected Map: {list(selected_map.keys())[0]} ({reason})")

                if reason:
                    self.reasoning_logs.append({
                        "agent": "script_developer",
                        "step": "map_selection",
                        "reasoning": reason
                    })

                common.log_node_result("step1_map_selection", result, self.session_timestamp, self.log_dir)
                return {"selected_map": selected_map}
        print("⚠️ Map selection failed. Falling back to default map (BarR 1.1).")
        default_map_path = ["map/files/barr_1.1.json"]
        default_map_data = common.load_json_from_db(default_map_path)
        if default_map_data:
            common.log_node_result("step1_map_selection", {"selected_map": default_map_data[0], "reason": "fallback_default"}, self.session_timestamp, self.log_dir)
            return {"selected_map": default_map_data[0]}
        return {"selected_map": {}}

    def place_units(self, state: ScriptDeveloperState) -> ScriptDeveloperState:
        print("\n[DeveloperS] 2. Placing Units...")
        map_data = state.get("selected_map", {})
        map_name = list(map_data.keys())[0] if map_data else "Unknown"
        user_intent = state.get("user_intent", {})
        gdd = state.get("gdd", {})
        
        terrain_search_query = f"Find the terrain information for {map_name}"
        current_terrain_info = self.db_caller.call(terrain_search_query)
        current_unit_info = []

        for i in range(5):
            prompt = ChatPromptTemplate.from_messages([
                ("system", PLACE_UNITS_PROMPT),
                ("user", """
                [GDD]
                {gdd}

                [Map Name] 
                {map_name}

                [User Intent]
                {user_intent}
                
                [Available Unit List]
                {unit_info}
                 
                [Terrain Info]
                {terrain_info}

                Calculate the map dimensions (Size * 512) and generate the scenario.
                If data is missing, search for it. Otherwise, generate placements.
                """)
            ])
            chain = prompt | self.client | self.parser
            result = chain.invoke({
                "gdd": json.dumps(gdd, ensure_ascii=False),
                "map_name": map_name,
                "unit_info": current_unit_info,
                "user_intent": user_intent,
                "terrain_info": current_terrain_info
            })
            action = result.get("action")
            if action == "call_db":
                query = f"Find units mathcing the query: {result.get('query', '').lower()}"
                print(f" [Unit Placement] Searching DB: '{query}'")
                
                found_paths = self.db_caller.call(query)
                retrieved_data = common.load_from_db(found_paths)
                
                if not retrieved_data:
                    print("⚠️ DB returned nothing. Retrying with different query might be needed.")
                    continue
                else:
                    if isinstance(retrieved_data, list):
                        current_unit_info.extend(retrieved_data)
                    else:
                        current_unit_info.append(retrieved_data)
            elif action == "finish":
                print("✅ All data present. Placement Generated.")
                target_keys = ["match_format", "unit_placement", "spawn_waves"]
                single_config = {k: result[k] for k in target_keys if k in result}

                reasoning = result.get("reasoning", "")
                if reasoning:
                    self.reasoning_logs.append({
                        "agent": "script_developer",
                        "step": "unit_placement",
                        "reasoning": reasoning
                    })

                final_unit_config = {
                    "unit_config": {
                        "normal": single_config
                    }
                }
                common.log_node_result("step2_unit_placement", result, self.session_timestamp, self.log_dir)
                return final_unit_config
        print("❌ Failed to place units within loop limit.")
        return {"unit_config": {}}

    def generate_rule_config(self, state: ScriptDeveloperState) -> ScriptDeveloperState: 
        print("\n[Developer] 3. Generating Rule Configurations...")

        gdd = state.get("gdd", {})
        map_data = state.get("selected_map", {})
        unit_config = state.get("unit_config", {}) 
        user_intent = state.get("user_intent", {})
        rule_list = gdd.get("rules", [])
        
        if not rule_list:
            print("   ⚠️ No rules found in gdd. Skipping config generation.")
            return {"rule_config": {}}
        rule_schemas = []
        for g in rule_list:
            rule_schemas.append({
                "name": g.get("name"),
                "description": g.get("role", ""),
                "config_schema": g.get("config_fmt") or g.get("config_format", {})
            })

        prompt = ChatPromptTemplate.from_messages([
            ("system", RULE_CONFIG_PROMPT),
            ("user", """
            [User Intent]
            {user_intent}

            [Active Rules & Schemas]:
            {rule_schemas}

            [Initial Unit Placement (Team Reference)]
            {unit_placement}

            [Map Info]
            {map_info}
            

            Based on the schemas above, generate the `customize` configuration for this scenario.
            """)
        ])

        chain = prompt | self.client | self.parser

        try:
            result = chain.invoke({
                "user_intent": user_intent,
                "rule_schemas": json.dumps(rule_schemas, indent=2),
                "unit_placement": json.dumps(unit_config, indent=2),
                "map_info": json.dumps(map_data)
            })

            config_reasoning = result.get("reasoning", "")
            if config_reasoning:
                self.reasoning_logs.append({
                    "agent": "script_developer",
                    "step": "rule_config",
                    "reasoning": config_reasoning if isinstance(config_reasoning, str) else str(config_reasoning)
                })

            common.log_node_result("step3_rule_config", result, self.session_timestamp, self.log_dir)

            # Wrap rule_config under "normal" key
            rule_cfg = result.get("rule_config", None) or result.get("customize", None) or {}
            return {"rule_config": {"normal": rule_cfg}}

        except Exception as e:
            print(f"[Error] Rule Config Generation Failed: {e}")
            return {"rule_config": {}}
    
    def get_condition(self, state: ScriptDeveloperState) -> ScriptDeveloperState:
        print("\n[Developer] 4. Generating Victory/Defeat Conditions...")
        user_intent = state.get("user_intent", {})
        gdd = state.get("gdd", {})
        map_data = state.get("selected_map", {})
        unit_config = state.get("unit_config", {})
        rule_config = state.get("rule_config", {})

        prompt = ChatPromptTemplate.from_messages([
            ("system", GET_CONDITION_PROMPT),
            ("user","""
            [User Intent]
            {user_intent}
        
            [GDD]
            {gdd}

            [Rule Configuration]
            {rule_config}
            
            [Unit Config]
            {unit_config}
            
            [Map Info]
            {map_info}
            
            Generate the `end_condition` and descriptions for the scenario.
            """)
        ])

        chain = prompt | self.client | self.parser

        result = chain.invoke({
            "user_intent": user_intent,
            "map_info": json.dumps(map_data, ensure_ascii=False),
            "gdd": json.dumps(gdd, ensure_ascii=False),
            "rule_config": json.dumps(rule_config, ensure_ascii=False),
            "unit_config": json.dumps(unit_config, ensure_ascii=False)
        })

        condition_reasoning = result.get("reasoning", "")
        if condition_reasoning:
            self.reasoning_logs.append({
                "agent": "script_developer",
                "step": "end_condition",
                "reasoning": condition_reasoning
            })

        common.log_node_result("step4_conditions", result, self.session_timestamp, self.log_dir)
        # Wrap under "normal" key
        return {
            "end_config": {"normal": result}
        }      
    
    def assemble_draft(self, state: ScriptDeveloperState) -> Dict:
        print("\n[Developer] 5. Finalizing Scenario JSON...")

        # 1. Map Data extraction
        selected_map_data = state.get("selected_map", {})
        map_name = list(selected_map_data.keys())[0] if selected_map_data else "Unknown Map"
        
        # 2. Global Data extraction
        unit_config_all = state.get("unit_config", {})
        rule_config_all = state.get("rule_config", {})
        end_config_all = state.get("end_config", {})
        
        # 3. Prepare Final Output
        final_output = {}
        difficulties = ["normal"]

        for diff in difficulties:

            u_conf = unit_config_all.get(diff, {})
            g_conf = rule_config_all.get(diff, {})
            e_conf = end_config_all.get(diff, {})
            
            # Build 'information' block
            info_block = {
                "map_name": map_name,
                "gdd": state.get("gdd", {}).get("gdd", "Custom Mode"),
                "description": e_conf.get("game_description", "No description available."),
                "match_format": u_conf.get("match_format", "1v1"),
                "decision": state.get("gdd", {}).get("decision", ["GroupMovement"]),
                "difficulty": diff,
                "fog_of_war": e_conf.get("fog_of_war", True)
            }
            
            # Build 'end_condition' block (Step 4 already structured this)
            end_cond = e_conf.get("end_condition", {
                "victory": "Destroy all enemies",
                "defeat": "Commander destroyed"
            })
            placement = u_conf.get("unit_placement", {})
            # g_conf may be the config directly, or wrapped in "customize"/"rule_config" key
            if g_conf and isinstance(g_conf, dict):
                customize_block = g_conf.get("customize", None) or g_conf.get("rule_config", None) or g_conf
            else:
                customize_block = {}
            scenario_json = {
                "information": info_block,
                "end_condition": end_cond,
                "unit_placement": placement,
                "customize": customize_block
            }
        

            final_output[diff] = scenario_json
            
        
        final_result = {
            "final_json": final_output
        }   
        common.log_node_result("step5_final_script", final_result, self.session_timestamp, self.log_dir)
        
        return {
            "final_json": final_output,
            "is_script_valid": False,
            "loop_count": 1  # Start at 1 so initial verify + MAX_LOOPS-1 refines = 3 total
        }
    
    def verify_script(self, state: ScriptDeveloperState) -> Dict:
        print("\n Verifying Script with Analyst...")
        current_json = state.get("final_json", {})

        analyst_input_state = {
            "current_script": current_json,
            "current_phase": "compiler",
            "loop_count": state.get("loop_count", 0),
            "target_diffs": state.get("refined_diffs", None)
        }
        
        try:
            # Call Analyst's verification logic
            result = self.analyst.verify_script(analyst_input_state)
            
            is_valid = result.get("game_script_valid", False)
            feedback_list = result.get("game_script_feedback", [])
            
            # Format feedback for LLM if it's a list
            feedback_str = "\n".join(feedback_list) if isinstance(feedback_list, list) else str(feedback_list)

            if is_valid:
                print("   ✅ Analyst: Script is VALID.")
                # Log successful validation
                self._log_feedback(
                    feedback="Script validation passed",
                    is_valid=True,
                    loop_count=state.get("loop_count", 0),
                    step_num=getattr(self, 'current_step_num', None)
                )
            else:
                print(f"   ❌ Analyst: Script is INVALID.\n   Errors: {feedback_str}")
                # Log failed validation
                self._log_feedback(
                    feedback=feedback_str,
                    is_valid=False,
                    loop_count=state.get("loop_count", 0),
                    step_num=getattr(self, 'current_step_num', None)
                )

            return {
                "is_script_valid": is_valid,
                "script_feedback": feedback_str
            }

        except Exception as e:
            print(f"   ⚠️ Analyst Verification Error: {e}")
            return {"is_script_valid": False, "script_feedback": str(e)}
        
    def refine_script(self, state: ScriptDeveloperState) -> Dict:
        print("\n[ScriptDev] 🔧 Refining Script...")

        current_json = state.get("final_json", {})
        feedback = state.get("script_feedback", "")
        user_intent = state.get("user_intent", "")
        loop_count = state.get("loop_count", 0) + 1

        # Single difficulty — always refine "normal"
        failed_diffs = {"normal"}

        prompt = ChatPromptTemplate.from_messages([
            ("system", REFINE_SCRIPT_PROMPT),
            ("user", """
            [User Intent]: {user_intent}
            [Error Feedback]: {feedback}
            [Current JSON]: {current_json}
            """)
        ])
        chain = prompt | self.client | self.parser

        merged_json = dict(current_json)
        any_fixed = False

        for diff in failed_diffs:
            if diff not in current_json:
                continue
            diff_feedback = "\n".join(
                line for line in feedback.splitlines()
                if f"[{diff.upper()}]" in line.upper() or f"[{diff}]" in line.lower()
            ) or feedback  # fallback to full feedback if no per-diff lines

            print(f"   Fixing [{diff.upper()}]...")
            try:
                fixed = chain.invoke({
                    "user_intent": user_intent,
                    "feedback": diff_feedback,
                    "current_json": json.dumps(current_json[diff], ensure_ascii=False)
                })
                if isinstance(fixed, dict):
                    merged_json[diff] = fixed
                    any_fixed = True
                    print(f"   ✅ [{diff.upper()}] Fixed")
                else:
                    print(f"   ⚠️ [{diff.upper()}] LLM returned non-dict, skipping")
            except Exception as e:
                print(f"   ❌ [{diff.upper()}] Fix failed: {e}")

        if any_fixed:
            print(f"   ✅ Script Refined (Loop {loop_count})")
        else:
            print(f"   ⚠️ No difficulties were fixed (Loop {loop_count})")

        return {
            "final_json": merged_json,
            "loop_count": loop_count,
            "is_script_valid": False,
            "refined_diffs": list(failed_diffs)
        }
    
    def _log_feedback(self, feedback: str, is_valid: bool, loop_count: int, step_num: int = None):
        """Log feedback for script validation/refinement."""
        feedback_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "source": "script_developer",
            "phase": "script_developer",
            "loop_count": loop_count,
            "is_valid": is_valid,
            "feedback": feedback
        }
        if step_num is not None:
            feedback_entry["step_num"] = step_num

        self.feedback_logs.append(feedback_entry)

        # Save immediately
        try:
            with open(self.feedback_log_path, "w", encoding="utf-8") as f:
                json.dump(self.feedback_logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"       ⚠️ Failed to save feedback log: {e}")

    def check_script_validity(self, state: ScriptDeveloperState):
        is_valid = state.get("is_script_valid", False)
        loop_count = state.get("loop_count", 0)
        MAX_LOOPS = 3

        if is_valid:
            return "valid"
        elif loop_count >= MAX_LOOPS:
            print(f"   ⚠️ Max refine loops ({MAX_LOOPS}) reached. Returning to router.")
            self._log_feedback(
                feedback=f"Max refine loops ({MAX_LOOPS}) reached — returning to router",
                is_valid=False,
                loop_count=loop_count,
                step_num=getattr(self, 'current_step_num', None)
            )
            return "max_retries"
        else:
            return "invalid"

    def run(self, user_intent: str, gdd: Dict, meta_feedback: str = None, step_num: int = None) -> Dict[str, Any]:
        self.current_step_num = step_num  # Store for use in other methods
        print(f"\n[ScriptDev] 🚀 Starting Script Generation Workflow for: '{user_intent}' (Step {step_num})")

        # If meta_feedback is provided, enhance the user_intent
        enhanced_intent = user_intent
        if meta_feedback:
            enhanced_intent = f"{user_intent}\n\n[Meta-Feedback from Previous Workflow]\n{meta_feedback}"
            print(f"[ScriptDev] 📝 Using meta-feedback to guide script generation")

        initial_state = {
            "user_intent": enhanced_intent,
            "gdd": gdd,
            "is_script_valid": False,
            "script_feedback": None,
            "loop_count": 0,
            "final_json": {},
            "selected_map": {},
            "unit_config": {},
            "rule_config": {},
            "end_config": {}
        }

        try:
            result_state = self.graph.invoke(initial_state)
            
            final_json = result_state.get("final_json", {})
            is_valid = result_state.get("is_script_valid", False)
            feedback = result_state.get("script_feedback", None)
            
            if final_json:
                output_dir = self.current_dir / "log" / self.session_timestamp / "result"
                os.makedirs(output_dir, exist_ok=True)
                
                saved_files = []
                for diff, data in final_json.items():
                    filename = f"scenario_{diff}.json"
                    file_path = output_dir / filename
                    
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    saved_files.append(str(file_path))
                    print(f"   💾 Saved: {file_path}")
                
                print("\n[ScriptDev] Script generation completed.")
            else:
                print("   ❌ Final JSON is empty.")
                is_valid = False
                feedback = "Script generation resulted in empty JSON."

            print(f"[System] Feedback logs saved to: {self.feedback_log_path}")

            return {
                "final_json": final_json,
                "is_valid": is_valid,
                "feedback": feedback,
                "feedback_history": self.feedback_logs,  # Include all feedback history
                "reasoning_log": self.reasoning_logs
            }

        except Exception as e:
            print(f"   ❌ Critical Error in ScriptDeveloper: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "final_json": {},
                "is_valid": False,
                "feedback": f"Critical Exception: {str(e)}"
            }

if __name__ == "__main__":
    import sys, glob

    if not os.getenv("OPENAI_API_KEY"):
        print("\nOPENAI_API_KEY is missing. Check .env file.\n")
        sys.exit(1)

    # Find the latest session or use arg
    current_dir = Path(__file__).resolve().parent.parent
    if len(sys.argv) > 1:
        TEST_SESSION = sys.argv[1]
    else:
        log_dirs = sorted(Path(current_dir / "log").glob("*_q0"))
        if not log_dirs:
            print("No session logs found.")
            sys.exit(1)
        TEST_SESSION = log_dirs[-1].name
        print(f"Using latest session: {TEST_SESSION}")

    designer_log_dir = current_dir / "log" / TEST_SESSION / "designer"
    gdd_files = list(designer_log_dir.glob("gdd_*.json"))

    if not gdd_files:
        print(f"No gdd files found in {designer_log_dir}")
        sys.exit(1)

    gdd_file = gdd_files[0]
    print(f"Loading gdd from: {gdd_file}")

    with open(gdd_file, "r", encoding="utf-8") as f:
        mock_gdd = json.load(f)

    mock_user_intent = mock_gdd.get("game_description", "")[:200]
    if not mock_user_intent:
        mock_user_intent = f"Create a {mock_gdd.get('gdd', 'custom')} GDD"

    print(f"GDD: {mock_gdd.get('gdd')}")
    print(f"Rules: {[g.get('name') for g in mock_gdd.get('rules', [])]}")
    print(f"Decision: {mock_gdd.get('decision', [])}")

    agent = ScriptDeveloperAgent(session_timestamp=TEST_SESSION)
    result = agent.run(user_intent=mock_user_intent, gdd=mock_gdd)

    final_script = result.get("final_json", {})
    if final_script:
        print("\nScript Generated Successfully!")
        for diff_key, diff_data in final_script.items():
            print(f"  {diff_key}: decision={diff_data.get('information',{}).get('decision','N/A')}")
    else:
        print(f"\nScript Generation Failed: {result.get('feedback', 'No feedback')}")