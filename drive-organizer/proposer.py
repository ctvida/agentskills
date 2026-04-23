import json
import csv
import os
import sys
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()  # optional: picks up .env in CWD if present, safe to keep
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    print(
        "Error: GEMINI_API_KEY environment variable is not set.\n"
        "Set it in your shell, pass it via your agent runtime's env config, "
        "or create a .env file in the skill directory.",
        file=sys.stderr
    )
    sys.exit(1)
genai.configure(api_key=_api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

def get_prompt(grouped_batch):
    return f"""
    You are an intelligent file organization agent working as a generalized skill for any drive (local or cloud).
    Your task is to analyze the following files and organize them into a clean, logical, BUT broad folder taxonomy.
    NOTE: You are receiving a batch of files grouped by their 'current_path'. Pay close attention to the 'current_path' to understand its context and favor existing structures.
    
    INSTRUCTIONS:
    1. Read the 'name' and context of the 'current_path' key to understand its domain.
    2. FAVOR EXISTING FOLDERS: If the current folder structure is already logical, reuse it. Do NOT invent new folders unless the current path is a generic mess (like '/Downloads/' or '/Desktop/'). Strongly prefer the hierarchy that already exists in the wild. If the current folder is too granular, you can propose moving files up to a higher-level folder.
    3. APPROPRIATE GRANULARITY: Do NOT go crazy with micro-folders. A folder with only 1 or 2 files defeats the purpose of organization. However, you MUST preserve critical contextual boundaries like Years for taxes or Semesters for academics (e.g., use '/Finance/Taxes/2020/' instead of just '/Finance/Taxes/' or the overly granular '/Finance/Taxes/2020/Q3/Receipts/').
    4. CATEGORIZE: Assign each file a proposed_path.
    5. AMBIGUOUS FILES: If a file's name and path lack enough context to categorize confidently (e.g., 'IMG_001.jpg' in 'Downloads', or 'document.pdf'), assign its proposed_path exactly as '/Needs_Content_Analysis/'. A secondary phase will later analyze its contents.
    
    FILES TO CATEGORIZE (Grouped by current_path): 
    {json.dumps(grouped_batch, indent=2)}
    
    Return ONLY valid JSON representing your decisions as a flat dictionary mapping 'id' to 'proposed_path':
    {{
        "file_123": "/Your_Generated_Category/Subcategory/",
        "file_456": "/Another_Category/"
    }}
    """

def generate_proposal(json_input, csv_output, threshold=20, batch_size=150):
    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        return

    with open(json_input, 'r') as f:
        manifest = json.load(f)

    print("Phase 1: Preparing flat list of files...")
    flat_files = []
    name_map = {}
    path_map = {}
    for item in manifest:
        file_name = item.get('file_name', '')
        if file_name.startswith('.') or file_name.lower() in ['thumbs.db', 'desktop.ini']:
            continue
        flat_files.append(item)
        name_map[item['file_id']] = file_name
        path_map[item['file_id']] = item.get('current_path', '/')

    actionable_decisions = []
    
    print(f"\nPhase 2: Agentic Divide & Conquer...")
    print(f" [ANALYZE] Total {len(flat_files)} files to categorize")
    
    # Slice into LLM-safe batches
    for i in range(0, len(flat_files), batch_size):
        batch_files = flat_files[i:i+batch_size]
        print(f"    -> Submitting chunk {i//batch_size + 1}/{len(flat_files)//batch_size + 1} ({len(batch_files)} files)...")
        
        grouped_batch = {}
        for f in batch_files:
            cp = f.get('current_path', '/')
            if cp not in grouped_batch:
                grouped_batch[cp] = []
            grouped_batch[cp].append({
                "id": f['file_id'],
                "name": f.get('file_name', '')
            })
            
        prompt = get_prompt(grouped_batch)
        backoff = 10
        max_retries = 3
        
        for attempt in range(max_retries + 1):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json"
                    )
                )
                
                batch_decisions = json.loads(response.text.strip())
                
                # Filter out pure no-ops and enrich data
                for file_id, proposed_path in batch_decisions.items():
                    current_path = path_map.get(file_id, '')
                    if proposed_path != current_path:
                        actionable_decisions.append({
                            'file_name': name_map.get(file_id, ''),
                            'file_id': file_id,
                            'current_path': current_path,
                            'proposed_path': proposed_path,
                            'approved': 'TRUE'
                        })
                
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
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(input_file):
        input_file = os.path.join(skill_dir, input_file)
    output_file = os.path.join(skill_dir, 'governed_actions.csv')
    generate_proposal(input_file, output_file, threshold=20, batch_size=150)