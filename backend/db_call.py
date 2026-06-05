import json
import os
from dotenv import load_dotenv
import common


class DBCall:
    def __init__(self, base_path: str = None, seed: int = None):
        load_dotenv()

        if base_path is None:
            self.base_path = os.path.join(os.path.dirname(__file__), "db")
        else:
            self.base_path = base_path

        self.client = common.get_client(seed=seed)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        import re

        # Remove markdown code blocks if present
        text = text.strip()

        # Try to extract JSON from ```json ... ``` or ``` ... ```
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_block_match:
            text = code_block_match.group(1).strip()

        # Try to find JSON object pattern
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)

        return json.loads(text)

    def _load_root_meta(self) -> dict:
        meta_path = os.path.join(self.base_path, "meta.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_folder_meta(self, folder: str) -> dict:
        meta_path = os.path.join(self.base_path, folder, "meta.json")
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _select_folder(self, query: str, root_meta: dict) -> str:
        folders_info = []
        for name, info in root_meta["folders"].items():
            folders_info.append(f"- {name}: {info['description']}")

        prompt = f"""Based on the query, select the most relevant folder.

Available folders:
{chr(10).join(folders_info)}

Query: {query}

Respond with JSON only:
{{"folder": "<folder_name>", "reason": "<brief reason>"}}"""
      
        response = self.client.invoke(prompt)
        result = self._extract_json(response.content)
        return result["folder"]

    def _select_files(self, query: str, folder: str, folder_meta: dict) -> list:
        if "details" not in folder_meta:
            return []

        items_info = []
        for name, info in folder_meta["details"].items():
            items_info.append(f"- {name}: {info['description']}")

        prompt = f"""Based on the query, select relevant files from this folder.

        Available items in '{folder}':
        {chr(10).join(items_info)}

        Query: {query}

        Respond with JSON only:
        {{"files": ["<item_name1>", "<item_name2>"], "reason": "<brief reason>"}}

        Select all relevant items. If query is general, select all."""

        response = self.client.invoke(prompt)
        result = self._extract_json(response.content)
        selected = result.get("files", [])

        file_paths = []
        selected_names = []
        for name in selected:
            if name in folder_meta["details"]:
                file_paths.append(folder_meta["details"][name]["file"])
                selected_names.append(name)

        return file_paths, selected_names

    def call(self, query: str, folder: str = None) -> list:
        if folder is None:
            root_meta = self._load_root_meta()
            folder = self._select_folder(query, root_meta)
        folder_meta = self._load_folder_meta(folder)
        file_paths, _ = self._select_files(query, folder, folder_meta)
        return file_paths

    def call_with_names(self, query: str, folder: str = None) -> tuple:
        """Returns (file_paths, selected_db_key_names)."""
        if folder is None:
            root_meta = self._load_root_meta()
            folder = self._select_folder(query, root_meta)
        folder_meta = self._load_folder_meta(folder)
        return self._select_files(query, folder, folder_meta)

if __name__ == "__main__":
    import sys
    
    # Define a test query
    TEST_QUERY = "Find a spatial reasoning game"

    print(f"\n{'='*50}")
    print(f"🚀 Starting DBCall Tool Test")
    print(f"{'='*50}")

    try:
        # 1. Check for API Key
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  Warning: OPENAI_API_KEY is not set.")
            print("   Please set it in your environment variables or .env file.")
        
        # 2. Initialize the Tool
        # If your 'db' folder is not in the default location, pass the path here.
        # e.g., tool = DBCall(base_path="/absolute/path/to/db")
        print("1️⃣  Initializing DBCall...")
        tool = DBCall()
        print(f"   -> Base DB Path: {tool.base_path}")

        # 3. Execute the Call
        print(f"\n2️⃣  Processing Query: '{TEST_QUERY}'")
        print("   -> Calling LLM to select folder and files...")
        
        file_paths = tool.call(TEST_QUERY)

        # 4. Print Results
        print(f"\n3️⃣  Search Results:")
        if file_paths:
            print(f"   ✅ Found {len(file_paths)} relevant file(s):")
            for i, path in enumerate(file_paths, 1):
                print(f"      [{i}] {path}")
        else:
            print("   ❓ No files found matching the query.")

    except FileNotFoundError as e:
        print(f"\n❌ FileNotFoundError:")
        print(f"   {e}")
        print("   -> Please check if your 'db' directory and 'meta.json' files exist.")
    except Exception as e:
        print(f"\n❌ An error occurred:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*50}")
    print("Test Finished")
    print(f"{'='*50}")