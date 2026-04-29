#!/usr/bin/env python3
"""Simple threaded HTTP server with skills API"""

import json
from pathlib import Path
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

SKILLS_DIR = Path.home() / ".hermes" / "skills"
WWW_DIR = Path(__file__).parent / "android" / "www"

def get_skills():
    skills = []
    if SKILLS_DIR.exists():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                skill_name = skill_dir.name
                skill_file = skill_dir / "SKILL.md"
                description = skill_name.replace('-', ' ').replace('_', ' ').title()
                if skill_file.exists():
                    for line in skill_file.read_text().split('\n')[:5]:
                        if line.startswith('# '):
                            description = line[2:].strip()
                            break
                skills.append({"name": skill_name, "description": description})
    return skills

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WWW_DIR), **kwargs)

    def do_GET(self):
        if self.path == '/api/skills':
            response = json.dumps(get_skills()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.end_headers()
            self.wfile.write(response)
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, format, *args):
        pass

def run_server(port=8080):
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"Server running on http://0.0.0.0:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
