import json
import csv
import os
import sys
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
    NOTE: You are receiving a mixed batch of files from across the entire system footprint. Even so, pay close attention to the 'current_path' of each file to understand its context and favor existing structures.
    
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

    print("Phase 1: Preparing flat list of files...")
    flat_files = []
    path_map = {}
    for item in manifest:
        file_name = item.get('file_name', '')
        if file_name.startswith('.') or file_name.lower() in ['thumbs.db', 'desktop.ini']:
            continue
        flat_files.append(item)
        path_map[item['file_id']] = item.get('current_path', '/')

    actionable_decisions = []
    
    print(f"\nPhase 2: Agentic Divide & Conquer...")
    print(f" [ANALYZE] Total {len(flat_files)} files to categorize")
    
    # Slice into LLM-safe batches
    for i in range(0, len(flat_files), batch_size):
        batch = flat_files[i:i+batch_size]
        print(f"    -> Submitting chunk {i//batch_size + 1}/{len(flat_files)//batch_size + 1} ({len(batch)} files)...")
        
        prompt = get_prompt(batch)
        backoff = 10
        max_retries = 3
        
        for attempt in range(max_retries + 1):
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
                break
                
            except Exception as e:
                error_msg = str(e).lower()
                if '429' in error_msg or 'quota' in error_msg or 'rate limit' in error_msg or 'exhausted' in error_msg:
                    if attempt < max_retries:
                        print(f"    -> Rate limit/quota issue. Retrying in {backoff}s (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        print(f"    -> Rate limit exhausted after {max_retries} retries. Skipping chunk.")
                else:
                    print(f"    -> Error analyzing chunk: {e}")
                    break

    print("\nPhase 3: Assembling Master Proposals...")
    with open(csv_output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['file_name', 'current_path', 'file_id', 'proposed_path', 'approved'])
        writer.writeheader()
        writer.writerows(actionable_decisions)
        
    print(f"Success! {len(actionable_decisions)} actionable moves generated -> {csv_output}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'audit.json'
    generate_proposal(input_file, 'governed_actions.csv', threshold=20, batch_size=50)