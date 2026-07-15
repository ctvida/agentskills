import json
import csv
import os
import re
import sys
import time
import yaml
from google import genai
from google.genai import types
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

client = genai.Client(api_key=_api_key)
# Most cost-efficient Gemini model; optimized for high-volume agentic tasks and data extraction.
# NOTE: This is a preview model — rate limits may be more restrictive than stable models.
# If you hit persistent 429s, fall back to gemini-2.5-flash-lite or gemini-2.0-flash.
MODEL = "gemini-3.1-flash-lite-preview"

# Marker for folders the taxonomy says need per-file content analysis
_AMBIGUOUS_CANONICAL = "/Needs_Content_Analysis/"

# Canonical vocabulary persisted across runs for consistent categories.
# Hand-edit to steer taxonomy; delete the file to start fresh.
TAXONOMY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taxonomy.yaml')


def load_prior_canonical_paths():
    """Canonical paths from previous runs (empty list if none)."""
    if not os.path.exists(TAXONOMY_FILE):
        return []
    with open(TAXONOMY_FILE) as f:
        data = yaml.safe_load(f) or {}
    return [p for p in data.get('canonical_paths', []) if p]


def save_canonical_paths(taxonomy):
    """Merge this run's canonical destinations into taxonomy.yaml.

    Deduped by normalize_path() (case/trailing-slash insensitive), since the LLM
    isn't guaranteed to reuse identical casing across runs. Prior (already
    established) casing wins over a new run's casing on conflict, so the
    persisted vocabulary stays stable instead of flip-flopping.
    """
    canon = {}
    for p in load_prior_canonical_paths() + list(taxonomy.values()):
        if normalize_path(p) == normalize_path(_AMBIGUOUS_CANONICAL):
            continue
        canon.setdefault(normalize_path(p), p.rstrip('/'))
    with open(TAXONOMY_FILE, 'w') as f:
        yaml.safe_dump({'canonical_paths': sorted(canon.values())}, f)

# Detects file names that differ only by a numeric index or timestamp
# (e.g. IMG_0042.jpg, DSC_1234.JPG, app_2024-01-01.log, frame_00012.png)
_SEQUENTIAL_RE = re.compile(
    r'^(.*?)(img_|dsc_|frame_|photo_|clip_|vid_)?(\d{3,}|\d{4}-\d{2}-\d{2})(.*?)(\.[a-zA-Z0-9]+)?$',
    re.IGNORECASE
)

def normalize_path(p):
    """Normalize a path for comparison: strip trailing slashes, lowercase."""
    return p.strip('/').lower() if p else ''

def is_sequential_name(name):
    """Return True if the file name looks like it belongs to a numbered/timestamp sequence."""
    return bool(_SEQUENTIAL_RE.match(os.path.splitext(name)[0] + (os.path.splitext(name)[1] or '')))

def build_folder_samples(flat_files):
    """
    Group all files by current_path, returning the full list of file names per folder.

    Exception: folders where the majority of file names are numerically sequential or
    timestamp-patterned (e.g. IMG_0001..IMG_0800) carry no extra semantic signal past
    the first few names. For those, cap at 8 names and annotate the remainder count.
    """
    folders = {}
    for f in flat_files:
        cp = f.get('current_path', '/')
        folders.setdefault(cp, []).append(f.get('file_name', ''))

    result = {}
    for cp, names in folders.items():
        sequential_count = sum(1 for n in names if is_sequential_name(n))
        if len(names) > 8 and sequential_count / len(names) > 0.7:
            result[cp] = names[:8] + [f"... and {len(names) - 8} more similarly-named files"]
        else:
            result[cp] = names
    return result

def get_taxonomy_prompt(folder_samples, prior_paths=None):
    prior_block = ""
    if prior_paths:
        prior_block = f"""
PRIOR CANONICAL VOCABULARY (established in previous runs — reuse these exact paths
wherever they fit; only invent a new canonical path when no prior path is appropriate):
{json.dumps(sorted(prior_paths), indent=2)}
"""
    return f"""{prior_block}
You are a file organization expert. You will receive the complete folder structure of a
Google Drive, with each folder path paired with the file names it currently contains.

Your task: produce a canonical folder taxonomy by consolidating semantically equivalent
or redundant folders into clean, descriptive paths.

RULES:
1. CONSOLIDATE: If two or more folders are semantically equivalent (e.g.
   "/Professional/Career/Job_Search/" and "/Career/Job_Search/"), merge them into
   ONE canonical path. Choose the clearest, most consistent name.

2. USE FILE NAMES: Use the listed file names to understand a folder's true domain.
   A folder named "/Misc/" containing W2s and tax returns should map to
   "/Finance/Taxes/" — not "/Misc/".

3. INVENT BETTER NAMES: You are encouraged to propose cleaner canonical paths that
   better reflect the content. Do not merely remap existing names if a better
   structure is apparent.

4. COMPLETENESS: Every input folder path MUST appear as a key in your output JSON.
   Do not omit any path.

5. GRANULARITY: Preserve meaningful context boundaries (e.g. years for tax records,
   semesters for academic files). Avoid micro-folders with only 1–2 files.

6. AMBIGUOUS FOLDERS: If a folder's name and files lack enough context to categorize
   confidently, map it to "{_AMBIGUOUS_CANONICAL}". A secondary per-file phase will
   handle those files.

CURRENT FOLDER STRUCTURE (path -> file names):
{json.dumps(folder_samples, indent=2)}

Return ONLY valid JSON mapping every source path to its canonical path:
{{
    "/source/path/": "/Canonical/Path/",
    ...
}}
"""

def get_prompt(grouped_batch, taxonomy):
    taxonomy_lines = "\n".join(
        f'  "{src}" -> "{canon}"'
        for src, canon in sorted(taxonomy.items())
        if normalize_path(canon) != normalize_path(_AMBIGUOUS_CANONICAL)
    )
    return f"""
You are an intelligent file organization agent. You are categorizing files that could
not be confidently classified by folder-level analysis alone.

CANONICAL FOLDER VOCABULARY
(your proposed_path values MUST use folder names from this list):
{taxonomy_lines}

INSTRUCTIONS:
1. Assign each file a proposed_path drawn from the CANONICAL FOLDER VOCABULARY above.
2. You MAY extend a canonical path with additional subfolders where clearly warranted
   (e.g. "/Finance/Taxes/2023/"), but MUST NOT introduce a new top-level or mid-level
   folder name that does not appear in the vocabulary.
3. Use the file name and its current_path as context to choose the best destination.
4. If the file is still genuinely ambiguous, assign "{_AMBIGUOUS_CANONICAL}".

FILES TO CATEGORIZE (Grouped by current_path):
{json.dumps(grouped_batch, indent=2)}

Return ONLY valid JSON mapping 'id' to 'proposed_path':
{{
    "file_123": "/Canonical/Path/",
    "file_456": "/Canonical/Path/Subfolder/"
}}
"""

def call_llm_with_retry(prompt, label="LLM call"):
    """Call the LLM with exponential backoff on rate-limit errors. Returns parsed JSON or None."""
    backoff = 30  # Start with 30s — enough to clear a 15 RPM window
    max_retries = 5
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text.strip())
        except Exception as e:
            error_msg = str(e).lower()
            if any(k in error_msg for k in ('429', 'quota', 'rate limit', 'exhausted', 'resource_exhausted')):
                if attempt < max_retries:
                    wait = backoff * (2 ** attempt)
                    print(f"    -> Rate limit [{label}]. Waiting {wait}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    print(f"    -> Rate limit exhausted after {max_retries} retries for [{label}]. Skipping.")
                    return None
            else:
                print(f"    -> Error [{label}]: {e}")
                return None

def build_taxonomy(folder_samples):
    """
    Phase 2: Call the LLM once with all folders + file names to produce a
    global {source_path -> canonical_path} taxonomy. Prints the mapping for inspection.
    """
    print(f"  [TAXONOMY] Sending {len(folder_samples)} folders to LLM for canonical mapping...")
    prior_paths = load_prior_canonical_paths()
    if prior_paths:
        print(f"  [TAXONOMY] Anchoring to {len(prior_paths)} canonical paths from {TAXONOMY_FILE}")
    prompt = get_taxonomy_prompt(folder_samples, prior_paths)
    taxonomy = call_llm_with_retry(prompt, label="taxonomy")
    if not taxonomy:
        print("  [TAXONOMY] Failed to build taxonomy. Ambiguous-mode fallback for all files.")
        return {}
    save_canonical_paths(taxonomy)
    print(f"  [TAXONOMY] Canonical vocabulary persisted to {TAXONOMY_FILE}")

    print(f"  [TAXONOMY] Canonical mapping established ({len(taxonomy)} folders):")
    for src, canon in sorted(taxonomy.items()):
        if normalize_path(src) == normalize_path(canon):
            print(f"    {'[=]':5s} {src}")
        else:
            print(f"    {src!r:50s} -> {canon!r}")
    return taxonomy

def generate_proposal(json_input, csv_output, batch_size=150):
    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        return

    with open(json_input, 'r') as f:
        manifest = json.load(f)

    # ── Phase 1: Prepare flat list ────────────────────────────────────────────
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

    print(f"  {len(flat_files)} files loaded.")

    # ── Phase 2: Build global taxonomy ───────────────────────────────────────
    print("\nPhase 2: Building global canonical taxonomy...")
    folder_samples = build_folder_samples(flat_files)
    taxonomy = build_taxonomy(folder_samples)

    # ── Phase 3: Apply taxonomy / per-file LLM for ambiguous files ───────────
    print("\nPhase 3: Applying taxonomy and categorizing ambiguous files...")
    actionable_decisions = []
    ambiguous_files = []

    for file_item in flat_files:
        file_id = file_item['file_id']
        current_path = path_map.get(file_id, '/')
        canonical = taxonomy.get(current_path)

        if canonical is None:
            # Path not in taxonomy (edge case) — send for per-file analysis
            ambiguous_files.append(file_item)
        elif normalize_path(canonical) == normalize_path(_AMBIGUOUS_CANONICAL):
            # Taxonomy explicitly flagged this whole folder as ambiguous
            ambiguous_files.append(file_item)
        else:
            # Apply taxonomy directly — no per-file LLM call needed
            if normalize_path(canonical) != normalize_path(current_path):
                actionable_decisions.append({
                    'file_name': name_map.get(file_id, ''),
                    'file_id': file_id,
                    'current_path': current_path,
                    'proposed_path': canonical.rstrip('/'),
                    'approved': 'TRUE'
                })

    direct_count = len(flat_files) - len(ambiguous_files)
    print(f"  {direct_count} files resolved via taxonomy directly.")
    print(f"  {len(ambiguous_files)} files queued for per-file analysis.")

    # Per-file LLM passes for ambiguous files
    if ambiguous_files and taxonomy:
        num_chunks = (len(ambiguous_files) + batch_size - 1) // batch_size
        for i in range(0, len(ambiguous_files), batch_size):
            chunk_num = i // batch_size + 1
            batch_files = ambiguous_files[i:i + batch_size]
            print(f"    -> Submitting ambiguous chunk {chunk_num}/{num_chunks} ({len(batch_files)} files)...")

            grouped_batch = {}
            for f in batch_files:
                cp = f.get('current_path', '/')
                grouped_batch.setdefault(cp, []).append({
                    "id": f['file_id'],
                    "name": f.get('file_name', '')
                })

            prompt = get_prompt(grouped_batch, taxonomy)
            batch_decisions = call_llm_with_retry(prompt, label=f"chunk {chunk_num}/{num_chunks}")
            if not batch_decisions:
                continue

            for file_id, proposed_path in batch_decisions.items():
                current_path = path_map.get(file_id, '')
                if normalize_path(proposed_path) != normalize_path(current_path):
                    actionable_decisions.append({
                        'file_name': name_map.get(file_id, ''),
                        'file_id': file_id,
                        'current_path': current_path,
                        'proposed_path': proposed_path.rstrip('/'),
                        'approved': 'TRUE'
                    })

            if chunk_num < num_chunks:
                time.sleep(5)

    # ── Phase 4: Write CSV ────────────────────────────────────────────────────
    print("\nPhase 4: Assembling Master Proposals...")
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
    generate_proposal(input_file, output_file, batch_size=150)