import os
import yaml
import json
import csv
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# Load API keys from your .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3.1-pro')

class UniversalOrganizeAgent:
    def __init__(self):
        self.manifest = []

    def scan_path(self, target_path):
        """Unified scanner for local or GDrive paths."""
        if target_path.startswith("gdrive://"):
            return self._scan_gdrive(target_path.replace("gdrive://", ""))
        return self._scan_local(target_path)

    def _scan_local(self, path):
        """Scans local directories, skipping protected hardware/photos."""
        for root, _, files in os.walk(path):
            if any(x in root.lower() for x in ["photos", "my pc", "usb", "sd card", ".git"]):
                continue
            for name in files:
                f_path = os.path.join(root, name)
                stats = os.stat(f_path)
                self.manifest.append({
                    'id': f_path, 'name': name, 'current_path': root,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    'created': datetime.fromtimestamp(stats.st_ctime).isoformat()
                })

    def get_semantic_batch(self, chunk):
        """The AI Agent's Semantic Brain."""
        prompt = f"""
        You are a Data Architect. Categorize these files for Christopher Phan.
        Use timestamps and folder context to identify project clusters.
        
        TAXONOMY:
        - /Education/Formal_Academic/ (Tuck, Dartmouth, MBA)
        - /Research/Exploration_Esoteric/ (Remote Viewing, CRV, Consciousness)
        - /Professional/Career/ (AI Engineering, Meta, Job Search)
        
        FILES: {json.dumps(chunk)}
        
        Return ONLY a JSON array: [{"id": "...", "proposed_path": "...", "action": "MOVE", "reason": "..."}]
        """
        response = model.generate_content(prompt)
        return json.loads(response.text.strip('```json').strip('```'))

    def run(self, target_path, output_csv="governed_actions.csv"):
        self.scan_path(target_path)
        batch_size = 50
        all_results = []
        for i in range(0, len(self.manifest), batch_size):
            chunk = self.manifest[i:i+batch_size]
            all_results.extend(self.get_semantic_batch(chunk))
        
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['file_name', 'proposed_path', 'action', 'id', 'reason', 'approved'])
            writer.writeheader()
            for r in all_results:
                r['approved'] = 'FALSE'
                writer.writerow(r)
        return output_csv