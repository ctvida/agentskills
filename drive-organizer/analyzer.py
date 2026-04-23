import os
import sys
import csv
import json
import tempfile
import time
import shutil
import google.generativeai as genai
from dotenv import load_dotenv

# Try to import scanner's auth logic if needed for GDrive
try:
    from scanner import get_gdrive_service
except ImportError:
    pass

load_dotenv()
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

genai.configure(api_key=_api_key)
# Using the requested model
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

def get_prompt(file_name, existing_taxonomy):
    taxonomy_list = "\n".join([f"- {path}" for path in existing_taxonomy])
    if not taxonomy_list:
        taxonomy_list = "- (No existing taxonomy found)"
        
    return f"""
    You are an intelligent file organization agent. Your task is to analyze the content of the attached file, named "{file_name}", and determine the best broad folder category for it.
    
    EXISTING FOLDERS:
    {taxonomy_list}
    
    INSTRUCTIONS:
    1. Analyze the content of the attached file to understand its domain.
    2. Prefer the EXISTING FOLDERS listed above. If there is a high probability match, use it exactly as listed.
    3. If there is not a high probability match for any existing folder hierarchy, you may invent your own logical folder.
    4. Provide the exact path you propose, e.g., "/Finance/Taxes/2020/".
    
    Return ONLY valid JSON representing your decision as a flat dictionary:
    {{
        "proposed_path": "/Your/Chosen/Path/"
    }}
    """

def run_analyzer(csv_input, is_local=False):
    if not os.path.exists(csv_input):
        print(f"Error: {csv_input} not found.")
        return

    print("Phase 1: Loading State & Extracting Taxonomy...")
    rows = []
    existing_taxonomy = set()
    ambiguous_files = []
    
    with open(csv_input, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            return
            
        if 'proposed_by' not in fieldnames:
            fieldnames.append('proposed_by')
            
        for row in reader:
            if 'proposed_by' not in row or not row['proposed_by']:
                row['proposed_by'] = 'proposer'
            rows.append(row)
            
            if row.get('proposed_path') == '/Needs_Content_Analysis/':
                ambiguous_files.append(row)
            else:
                existing_taxonomy.add(row.get('proposed_path', '/'))

    if not ambiguous_files:
        print("No ambiguous files found in the CSV. Everything is categorized!")
        return

    print(f"\nPhase 2: Cost Estimation Pre-flight Check")
    service = None
    if not is_local:
        try:
            service = get_gdrive_service()
        except NameError:
            print("Error: Could not import get_gdrive_service from scanner.py.")
            sys.exit(1)

    total_size_bytes = 0
    valid_ambiguous = []
    
    print(f"Scanning {len(ambiguous_files)} files slated for analysis...")
    
    for row in ambiguous_files:
        file_id = row['file_id']
        size = 0
        if is_local:
            if os.path.exists(file_id):
                size = os.path.getsize(file_id)
                total_size_bytes += size
                valid_ambiguous.append((row, size))
            else:
                print(f"  Warning: Local file not found: {file_id}")
        else:
            try:
                file_meta = service.files().get(fileId=file_id, fields='size').execute()
                size = int(file_meta.get('size', 0))
                total_size_bytes += size
                valid_ambiguous.append((row, size))
            except Exception as e:
                print(f"  Warning: Could not access GDrive file {row.get('file_name', file_id)}: {e}")

    total_mb = total_size_bytes / (1024 * 1024)
    print("\n--- Pre-flight Cost Estimation ---")
    print(f"Total files to analyze: {len(valid_ambiguous)}")
    print(f"Total estimated size: {total_mb:.2f} MB")
    print("----------------------------------")
    
    choice = input("Proceed with analysis? (y/N): ").strip().lower()
    if choice != 'y':
        print("Analysis aborted by user.")
        return

    print(f"\nPhases 3-5: Fetch, Analyze, and Update")
    temp_dir = tempfile.mkdtemp()
    
    try:
        for idx, (row, size) in enumerate(valid_ambiguous):
            file_name = row['file_name']
            file_id = row['file_id']
            print(f"\n[{idx+1}/{len(valid_ambiguous)}] Analyzing: {file_name} ({size/(1024*1024):.2f} MB)")
            
            local_path = None
            if is_local:
                local_path = file_id
            else:
                local_path = os.path.join(temp_dir, file_name)
                print("  -> Downloading from Google Drive...")
                import io
                from googleapiclient.http import MediaIoBaseDownload
                try:
                    request = service.files().get_media(fileId=file_id)
                    with open(local_path, "wb") as f_out:
                        downloader = MediaIoBaseDownload(f_out, request)
                        done = False
                        while done is False:
                            status, done = downloader.next_chunk()
                except Exception as e:
                    print(f"  -> Error downloading (might be a native Google Doc, which requires export instead): {e}")
                    continue
            
            gemini_file = None
            try:
                print("  -> Uploading to Gemini API...")
                gemini_file = genai.upload_file(local_path, display_name=file_name)
                
                while gemini_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gemini_file = genai.get_file(gemini_file.name)
                
                if gemini_file.state.name == "FAILED":
                    print("  -> Gemini failed to process file.")
                    continue
                    
                print("  -> Generating categorization proposal...")
                prompt = get_prompt(file_name, list(existing_taxonomy))
                
                response = model.generate_content(
                    [gemini_file, prompt],
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json"
                    )
                )
                
                decision = json.loads(response.text.strip())
                new_path = decision.get("proposed_path")
                
                if new_path:
                    print(f"  -> Analyzed and mapped to: {new_path}")
                    row['proposed_path'] = new_path
                    row['proposed_by'] = 'analyzer'
                    existing_taxonomy.add(new_path)
                else:
                    print("  -> Failed to get a valid path from LLM.")
                    
            except Exception as e:
                print(f"  -> Error analyzing file: {e}")
            finally:
                if gemini_file:
                    try:
                        genai.delete_file(gemini_file.name)
                        print("  -> Deleted file from Gemini.")
                    except Exception as e:
                        print(f"  -> Failed to delete from Gemini: {e}")
                        
                if not is_local and local_path and os.path.exists(local_path):
                    os.remove(local_path)
                    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\nPhase 6: Saving updated CSV...")
    with open(csv_input, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Success! {csv_input} updated.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyzer.py governed_actions.csv [--local]")
        sys.exit(1)
        
    csv_file = sys.argv[1]
    is_local = False
    if len(sys.argv) >= 3 and sys.argv[2] == "--local":
        is_local = True
        
    run_analyzer(csv_file, is_local=is_local)
