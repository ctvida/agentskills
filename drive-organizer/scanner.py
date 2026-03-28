import os
import sys
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_gdrive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # Check if the scopes in the token match the requested scopes
        if creds and creds.scopes != SCOPES:
            print(f"Scope mismatch detected. Token scopes: {creds.scopes}, Requested scopes: {SCOPES}")
            creds = None # Force re-authentication
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}. Re-authenticating...")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def scan_gdrive():
    service = get_gdrive_service()
    
    print("Initiating top-down crawl from My Drive root...", file=sys.stderr)
    
    manifest = []
    
    # Queue stores tuples of (folder_id, folder_path)
    # Start at 'root' representing My Drive
    folder_queue = [('root', '')]
    visited_folders = set()
    
    while folder_queue:
        current_folder_id, current_path = folder_queue.pop(0)
        
        if current_folder_id in visited_folders:
            continue
        visited_folders.add(current_folder_id)
        
        page_token = None
        while True:
            # Query for items that have current_folder_id as parent AND we own them AND they aren't trashed
            q = f"'{current_folder_id}' in parents and trashed = false and 'me' in owners"
            res = service.files().list(
                q=q, 
                fields="nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime)", 
                pageToken=page_token,
                pageSize=1000  # Maximize page size for efficiency
            ).execute()
            
            for f in res.get('files', []):
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    new_path = f"{current_path}/{f['name']}"
                    folder_queue.append((f['id'], new_path))
                else:
                    # File
                    manifest_path = current_path if current_path else "/"
                    manifest.append({
                        'file_id': f['id'],
                        'file_name': f['name'],
                        'current_path': manifest_path,
                        'modified': f['modifiedTime'],
                        'md5': f.get('md5Checksum')
                    })
                    
            page_token = res.get('nextPageToken')
            if not page_token: break
            
        if len(visited_folders) % 50 == 0:
            print(f"Scanned {len(visited_folders)} folders. Found {len(manifest)} files so far...", file=sys.stderr)
            
    print(f"Extraction complete. Scanned {len(visited_folders)} folders and found {len(manifest)} files.", file=sys.stderr)
    return manifest

def scan_local(root_path):
    manifest = []
    
    abs_path = os.path.abspath(root_path)
    drive, path_part = os.path.splitdrive(abs_path)
    if path_part in ['\\', '/']:
        print("Error: Scanning a root system directory is blocked to prevent reorganizing critical system files.", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(root_path):
        print(f"Path not found: {root_path}", file=sys.stderr)
        return manifest
        
    base_prefix = abs_path
    for current_path, dirs, files in os.walk(base_prefix):
        for f in files:
            full_path = os.path.join(current_path, f)
            try:
                stat = os.stat(full_path)
                rel_path = current_path[len(base_prefix):].replace("\\", "/")
                if not rel_path: 
                    rel_path = "/"
                elif not rel_path.startswith("/"): 
                    rel_path = "/" + rel_path
                    
                manifest.append({
                    'file_id': full_path,
                    'file_name': f,
                    'current_path': rel_path,
                    'modified': stat.st_mtime,
                    'md5': None
                })
            except Exception:
                pass
    print(f"Extraction complete. Found {len(manifest)} local files.", file=sys.stderr)
    return manifest

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scanner.py [gdrive://root | /local/path]")
        sys.exit(1)
        
    path = sys.argv[1]
    if path.startswith("gdrive://"):
        data = scan_gdrive()
    else:
        if not os.path.isdir(path):
            print(f"Error: Directory {path} not found.", file=sys.stderr)
            sys.exit(1)
        data = scan_local(path)
        
    print(json.dumps(data, indent=2))