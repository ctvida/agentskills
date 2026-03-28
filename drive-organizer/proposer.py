import json
import csv
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

def get_prompt(batch):
    return f"""
    You are an intelligent file organization agent working as a generalized skill for any drive (local or cloud).
    Your task is to analyze the following files and organize them into a clean, logical, BUT broad folder taxonomy.
    
    INSTRUCTIONS:
    1. Read the 'file_name' and 'current_path' of each file to understand its context and domain.
    2. FAVOR EXISTING FOLDERS: Look closely at the 'current_path'. If the current folder structure is already logical, reuse it. Do NOT invent new folders unless the current path is a generic mess (like '/Downloads/' or '/Desktop/'). Strongly prefer the hierarchy that already exists in the wild.
    3. PREVENT MICRO-FOLDERS: Do NOT go crazy with granularity. A folder structure with only 1 or 2 files per folder defeats the purpose of organization. Group files into broad, high-level categories (e.g., '/Finance/Taxes/' instead of '/Finance/Taxes/2020/Q3/Receipts/'). Only create a new subfolder if there is a massive density of files that strictly demand it.
    4. CATEGORIZE: Assign each file a 'proposed_path'. Keep the taxonomy broad.
    5. AMBIGUOUS FILES: If a file's name and path lack enough context to categorize confidently (e.g., 'IMG_001.jpg' in 'Downloads', or 'document.pdf'), assign its proposed_path exactly as '/Needs_Content_Analysis/'. A secondary phase will later analyze its contents.
    
    FILES TO CATEGORIZE: 
    {json.dumps(batch, indent=2)}
    
    Return ONLY valid JSON representing your decisions in this exact format:
    [{{
        "file_name": "...", 
        "file_id": "...", 
        "proposed_path": "/Your_Generated_Category/Subcategory/"
    }}]
    """

def generate_proposal(json_input, csv_output, threshold=20, batch_size=50):
    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        return

    with open(json_input, 'r') as f:
        manifest = json.load(f)

    print("Phase 1: Grouping files by current path...")
    path_groups = {}
    path_map = {}
    for item in manifest:
        cp = item.get('current_path', '/')
        if cp not in path_groups:
            path_groups[cp] = []
        path_groups[cp].append(item)
        path_map[item['file_id']] = cp

    actionable_decisions = []
    
    print(f"\nPhase 2: Agentic Divide & Conquer...")
    for current_path, files in path_groups.items():
        print(f" [ANALYZE] {current_path} ({len(files)} files)")
        
        # Slice into LLM-safe batches
        for i in range(0, len(files), batch_size):
            batch = files[i:i+batch_size]
            print(f"    -> Submitting chunk {i//batch_size + 1}/{len(files)//batch_size + 1} ({len(batch)} files)...")
            
            prompt = get_prompt(batch)
            try:
                response = model.generate_content(prompt)
                # Cleanup markdown blocks if AI includes them
                clean_json = response.text.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.startswith("```"):
                    clean_json = clean_json[3:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                    
                batch_decisions = json.loads(clean_json.strip())
                
                # Filter out pure no-ops and enrich data
                for d in batch_decisions:
                    d['current_path'] = path_map.get(d.get('file_id'), '')
                    d['approved'] = 'TRUE' # Default to Opt-Out Governance
                    if d.get('proposed_path') != d['current_path']:
                        actionable_decisions.append(d)
                
                # Sleep to protect API limits over huge drives
                time.sleep(2)
                
            except Exception as e:
                print(f"    -> Error analyzing chunk: {e}")

    print("\nPhase 3: Assembling Master Proposals...")
    with open(csv_output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['file_name', 'current_path', 'file_id', 'proposed_path', 'approved'])
        writer.writeheader()
        writer.writerows(actionable_decisions)
        
    print(f"Success! {len(actionable_decisions)} actionable moves generated -> {csv_output}")

if __name__ == "__main__":
    generate_proposal('audit.json', 'governed_actions.csv', threshold=20, batch_size=50)