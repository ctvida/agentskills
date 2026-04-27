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

def normalize_path(p):
    """Normalize a path for comparison: strip trailing slashes, lowercase."""
    return p.strip('/').lower() if p else ''

def get_prompt(grouped_batch):
    return f"""
    You are an intelligent file organization agent working as a generalized skill for any drive (local or cloud).
    Your task is to analyze the following files and organize them into a clean, logical, BUT broad folder taxonomy.
    NOTE: You are receiving a batch of files grouped by their 'current_path'. Pay close attention to the 'current_path' to understand its context and favor existing structures.
    
    INSTRUCTIONS:
    1. Read the 'name' and 'current_path' of each file to understand its domain.

    2. CONSOLIDATE FIRST: Before deciding where a file belongs, look across ALL
       the current_paths in this batch. If two or more folders are semantically
       equivalent (e.g. "/Admin/Financial Planning" and "/Personal/Finance", or
       "/Work/Projects" and "/Professional/Projects"), you MUST consolidate them
       into a single canonical folder. Choose the name that is clearest and most
       consistent with the majority of other paths you can see.

    3. FAVOR EXISTING CANONICAL FOLDERS: Once you have identified the canonical
       set of folders from step 2, reuse them. Do not invent a new folder if a
       canonical one already covers the domain.

    4. APPROPRIATE GRANULARITY: Preserve meaningful context boundaries such as
       years for financial records or semesters for academic files (e.g.,
       "/Finance/Taxes/2020/" not just "/Finance/Taxes/"). However, do not create
       micro-folders with only 1-2 files unless the context clearly demands it.

    5. AMBIGUOUS FILES: If a file's name and path lack enough context to
       categorize confidently, assign proposed_path as "/Needs_Content_Analysis/".
       A secondary phase will analyze its content later.
    
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
                    if normalize_path(proposed_path) != normalize_path(current_path):
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