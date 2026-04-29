import sys
import csv
import os
import shutil


def get_or_create_folder(service, folder_name, parent_id):
    # Escape single quotes in folder name for the query
    safe_name = folder_name.replace("'", "\\'")
    q = f"name='{safe_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = service.files().list(q=q, fields="files(id)").execute()
    files = res.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        # Create folder if it doesn't exist
        print(f"    [+] Creating missing folder: {folder_name} inside {parent_id}")
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def resolve_path_to_folder_id(service, path):
    parts = [p for p in path.split('/') if p]
    current_parent = 'root' # Start at My Drive root
    for part in parts:
        current_parent = get_or_create_folder(service, part, current_parent)
    return current_parent

def move_gdrive_file(service, file_id, new_parent_id):
    file = service.files().get(fileId=file_id, fields='parents').execute()
    previous_parents = ",".join(file.get('parents', []))
    
    service.files().update(
        fileId=file_id,
        addParents=new_parent_id,
        removeParents=previous_parents,
        fields='id, parents'
    ).execute()


def normalize_path(p):
    """Normalize a path for comparison: strip trailing slashes, lowercase."""
    return p.strip('/').lower() if p else ''

def execute_approved_moves(csv_path, is_local=False, local_base="/"):
    if is_local:
        abs_base = os.path.abspath(local_base)
        drive, path_part = os.path.splitdrive(abs_base)
        if path_part in ['\\', '/']:
            print("Error: Using a root system directory as local_base is blocked to prevent reorganizing critical system files.")
            sys.exit(1)

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    if not is_local:
        from scanner import get_gdrive_service
        service = get_gdrive_service()
    else:
        service = None
    folder_cache = {}
    moved_source_paths = set()

    with open(csv_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('approved', '').strip().upper() == 'TRUE':
                file_id = row['file_id']
                current = row.get('current_path', '')
                target_path = row['proposed_path']

                if normalize_path(current) == normalize_path(target_path):
                    print(f"  [SKIP] {row['file_name']} — already in correct location.")
                    continue

                print(f"COMMITTING: Moving {row['file_name']} to {target_path}...")
                
                try:
                    if is_local:
                        # target_path is like /Category/Subcategory/
                        # file_id is the full absolute local path
                        full_target_dir = os.path.normpath(os.path.join(local_base, target_path.strip("/")))
                        if not os.path.exists(full_target_dir):
                            os.makedirs(full_target_dir, exist_ok=True)
                        dest_file = os.path.join(full_target_dir, row['file_name'])
                        shutil.move(file_id, dest_file)
                        print(f" -> Success!")
                    else:
                        if target_path not in folder_cache:
                            folder_cache[target_path] = resolve_path_to_folder_id(service, target_path)
                        target_folder_id = folder_cache[target_path]
                        move_gdrive_file(service, file_id, target_folder_id)
                        print(f" -> Success!")
                except Exception as e:
                    print(f" -> Failed: {e}")
                else:
                    moved_source_paths.add(current)

    # ── Orphaned folder cleanup ───────────────────────────────────────────────
    print("\nCleaning up orphaned (now-empty) source folders...")
    cleanup_orphaned_folders(moved_source_paths, is_local=is_local,
                             local_base=local_base, service=service)


def cleanup_orphaned_folders(source_paths, is_local=False, local_base="/", service=None):
    """
    Delete folders that had all their files moved out, leaving them empty.

    - Scoped only to paths that were actual move sources in the CSV.
    - Processed deepest-first so children are cleaned before parents.
    - GDrive: queries for non-trashed children before deleting.
    - Local:  relies on os.rmdir(), which refuses to remove non-empty dirs.
    - The root / local_base itself is never touched.
    """
    if not source_paths:
        print("  Nothing to clean up.")
        return

    # Sort deepest paths first so children are deleted before parents
    sorted_paths = sorted(source_paths, key=lambda p: p.count('/'), reverse=True)

    deleted = 0
    skipped = 0

    for path in sorted_paths:
        if not path or normalize_path(path) in ('', '/'):
            continue  # Never touch root

        try:
            if is_local:
                full_path = os.path.normpath(os.path.join(local_base, path.strip('/')))
                abs_base = os.path.abspath(local_base)
                if os.path.abspath(full_path) == abs_base:
                    continue  # Never delete the base itself
                if not os.path.isdir(full_path):
                    continue  # Already gone
                os.rmdir(full_path)  # Raises OSError if not empty — safe by design
                print(f"  [DEL] {path}")
                deleted += 1
            else:
                if service is None:
                    break
                # Resolve folder ID from path, skip if it doesn't exist
                try:
                    folder_id = _resolve_existing_folder_id(service, path)
                except LookupError:
                    continue  # Folder doesn't exist on Drive — already gone

                # Check for any non-trashed children
                q = f"'{folder_id}' in parents and trashed=false"
                res = service.files().list(q=q, fields="files(id)", pageSize=1).execute()
                if res.get('files'):
                    print(f"  [SKIP] {path} — still has children.")
                    skipped += 1
                    continue

                service.files().delete(fileId=folder_id).execute()
                print(f"  [DEL] {path}")
                deleted += 1

        except OSError as e:
            # os.rmdir raises OSError for non-empty dirs — expected, not an error
            print(f"  [SKIP] {path} — not empty or inaccessible ({e})")
            skipped += 1
        except Exception as e:
            print(f"  [ERR] {path} — {e}")

    print(f"  Done: {deleted} folder(s) removed, {skipped} skipped (not empty).")


def _resolve_existing_folder_id(service, path):
    """
    Walk a Drive path and return the folder ID. Raises LookupError if any
    segment doesn't exist (unlike resolve_path_to_folder_id which creates them).
    """
    parts = [p for p in path.split('/') if p]
    current_parent = 'root'
    for part in parts:
        safe_name = part.replace("'", "\\'")
        q = (f"name='{safe_name}' and '{current_parent}' in parents "
             f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
        res = service.files().list(q=q, fields="files(id)", pageSize=1).execute()
        files = res.get('files', [])
        if not files:
            raise LookupError(f"Folder segment not found: {part!r} in {path}")
        current_parent = files[0]['id']
    return current_parent


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 committer.py governed_actions.csv [--local /base/path]")
    else:
        csv_file = sys.argv[1]
        is_local = False
        local_base = "/"
        if len(sys.argv) >= 4 and sys.argv[2] == "--local":
            is_local = True
            local_base = sys.argv[3]
        execute_approved_moves(csv_file, is_local=is_local, local_base=local_base)