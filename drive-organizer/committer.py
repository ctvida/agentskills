import sys
import csv
import os
from scanner import get_gdrive_service

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

import shutil

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

    service = get_gdrive_service() if not is_local else None
    folder_cache = {}

    with open(csv_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('approved', '').strip().upper() == 'TRUE':
                file_id = row['file_id']
                target_path = row['proposed_path']
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