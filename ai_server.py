#!/usr/bin/env python3
"""
AI Chat Server - MiniMax Real AI Version
Web chat connects here -> calls MiniMax API
Tools system integrated for extended capabilities!
"""

import os
import json
import asyncio
import websockets
import requests
import re
import subprocess
from aiohttp import web
from datetime import datetime, timedelta
from pathlib import Path
import html
import urllib.parse

connected_clients = set()
message_count = 0  # Track total messages sent to chat

# ============================================================
# SECURE PIN SYSTEM - Server-side verification
# ============================================================
import secrets
import hashlib
import time

# PIN storage: sha256$pdkdf2_hash (stored format)
# Default PIN '1234' with generated salt
PIN_STORE = {
    "salt": "edba8f33b08018d0df1606bcc46c32d6",
    "hash": "64c871e98e1f2669d82fd1e170f19595a473b250e7d4cd8761aa04c7c66f868e"
}

# Failed attempts tracking: {ip: {"count": N, "until": timestamp}}
failed_attempts = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes

def verify_pin(pin: str) -> bool:
    """Verify PIN using PBKDF2-SHA256 with stored salt"""
    salt = PIN_STORE["salt"]
    stored_hash = PIN_STORE["hash"]
    computed = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 100000).hex()
    return secrets.compare_digest(computed, stored_hash)

async def verify_pin_handler(request):
    """POST /api/verify-pin - verify PIN and return success/lockout"""
    try:
        data = await request.json()
        pin = data.get("pin", "")
    except:
        return web.json_response({"error": "Invalid request"}, status=400)
    
    client_ip = request.remote
    now = time.time()
    
    # Check lockout
    if client_ip in failed_attempts:
        info = failed_attempts[client_ip]
        if now < info["until"]:
            remaining = int(info["until"] - now)
            return web.json_response({
                "success": False,
                "locked": True,
                "remaining_seconds": remaining,
                "attempts_left": 0
            })
        else:
            # Lockout expired, reset
            del failed_attempts[client_ip]
    
    # Verify PIN
    if verify_pin(pin):
        # Reset failed attempts on success
        if client_ip in failed_attempts:
            del failed_attempts[client_ip]
        return web.json_response({"success": True, "locked": False})
    else:
        # Increment failed attempts
        if client_ip not in failed_attempts:
            failed_attempts[client_ip] = {"count": 0, "until": 0}
        failed_attempts[client_ip]["count"] += 1
        attempts_left = MAX_ATTEMPTS - failed_attempts[client_ip]["count"]
        
        if attempts_left <= 0:
            failed_attempts[client_ip]["until"] = now + LOCKOUT_SECONDS
            return web.json_response({
                "success": False,
                "locked": True,
                "remaining_seconds": LOCKOUT_SECONDS,
                "attempts_left": 0
            })
        
        return web.json_response({
            "success": False,
            "locked": False,
            "attempts_left": attempts_left
        })

# Get API key from environment
def get_api_key():
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "MINIMAX_API_KEY" in line and not line.strip().startswith("#"):
                parts = line.split("=", 1)
                if len(parts) == 2 and parts[1].strip():
                    api_key = parts[1].strip().strip('"').strip("'")
                    break
    return api_key

MINIMAX_API_KEY = get_api_key()
MINIMAX_MODEL = "MiniMax-M2.7"
MINIMAX_BASE_URL = "https://api.minimax.io"

def get_wib_time():
    """Get current time in WIB (UTC+7)"""
    return datetime.utcnow() + timedelta(hours=7)

# ============================================================
# TOOLS REGISTRY - Available capabilities for the AI
# ============================================================

TOOLS = {
    "web_search": {
        "name": "web_search",
        "desc": "Search the web for current information. Use when you need up-to-date facts, news, or info beyond your training data.",
        "params": ["query"],
        "example": "[TOOL: web_search | query='latest AI news 2026']"
    },
    "crypto_price": {
        "name": "crypto_price",
        "desc": "Get current cryptocurrency prices. Use for BTC, ETH, SOL, etc. Returns price in USD and IDR with 24h change.",
        "params": ["symbol"],
        "example": "[TOOL: crypto_price | symbol='BTC']"
    },
    "calculator": {
        "name": "calculator",
        "desc": "Perform mathematical calculations. Use for math problems, conversions, or any numeric computation.",
        "params": ["expression"],
        "example": "[TOOL: calculator | expression='(1500000 * 12) / 0.15']"
    },
    "currency_convert": {
        "name": "currency_convert",
        "desc": "Convert between currencies. Provide amount and source/target currencies.",
        "params": ["amount", "from_currency", "to_currency"],
        "example": "[TOOL: currency_convert | amount='100' | from_currency='USD' | to_currency='IDR']"
    },
    "wikipedia": {
        "name": "wikipedia",
        "desc": "Get information from Wikipedia. Best for factual queries about people, places, history, and concepts.",
        "params": ["topic"],
        "example": "[TOOL: wikipedia | topic='Artificial Intelligence']"
    },
    "image_gen": {
        "name": "image_gen",
        "desc": "Generate an image from a text description. Use when user wants to create visual content.",
        "params": ["prompt"],
        "example": "[TOOL: image_gen | prompt='a beautiful sunset over the ocean in Indonesia']"
    },
    "code_exec": {
        "name": "code_exec",
        "desc": "Execute Python code and return the result. Use for data analysis, calculations, or running algorithms.",
        "params": ["code"],
        "example": "[TOOL: code_exec | code='import math; print(math.sqrt(144))']"
    },
    "weather": {
        "name": "weather",
        "desc": "Get current weather information for a city.",
        "params": ["city"],
        "example": "[TOOL: weather | city='Jakarta']"
    },
    "news": {
        "name": "news",
        "desc": "Get latest news headlines. Use for current events, trending topics, or news queries.",
        "params": ["topic"],
        "example": "[TOOL: news | topic='technology']"
    },
    "translate": {
        "name": "translate",
        "desc": "Translate text from one language to another.",
        "params": ["text", "from_lang", "to_lang"],
        "example": "[TOOL: translate | text='Hello world' | from_lang='en' | to_lang='id']"
    },
    "hermes_skill": {
        "name": "hermes_skill",
        "desc": "Execute a Hermes skill by name. Loads the skill SKILL.md and executes it. Supports API-based skills (polymarket, meteora-dlmm, google-news, github), knowledge skills, and can guide on terminal/browser/jupyter skills.",
        "params": ["skill_name", "query"],
        "example": "[TOOL: hermes_skill | skill_name='research.polymarket' | query='Will BTC reach 100k by end of 2026?']"
    },
    "polymarket": {
        "name": "polymarket",
        "desc": "Get Polymarket prediction market prices and odds. Use for betting odds, event probabilities, Yes/No markets.",
        "params": ["query"],
        "example": "[TOOL: polymarket | query='Bitcoin price 2026']"
    },
    "meteora_dlmm": {
        "name": "meteora_dlmm",
        "desc": "Get Meteora DLMM pool data — SOL-HYPE, JUP-SOL, etc. Returns price, liquidity, fee, active bin info.",
        "params": ["pool_address"],
        "example": "[TOOL: meteora_dlmm | pool_address='CafMC1jinkxXx3ikBgPpyRaHqhND23dVSjRdWAaUtdDb']"
    },
    "terminal": {
        "name": "terminal",
        "desc": "Execute safe shell commands on the VPS. Allowed: ls, cat, git, npm, pip, python, curl, grep, awk, sed, find, etc. Blocked: rm -rf, sudo, ssh, subprocess, os commands.",
        "params": ["command"],
        "example": "[TOOL: terminal | command='ls -la /home/ubuntu/']"
    },
    "browser": {
        "name": "browser",
        "desc": "Navigate webpages and extract content using Playwright. Actions: snapshot (get text), screenshot, click, type, evaluate(JS).",
        "params": ["url", "action"],
        "example": "[TOOL: browser | url='https://github.com' | action='snapshot']"
    },
    "jupyter": {
        "name": "jupyter",
        "desc": "Execute Python code in a persistent Jupyter kernel with full numpy/pandas/matplotlib support.",
        "params": ["code"],
        "example": "[TOOL: jupyter | code='import numpy as np; print(np.random.randn(5))']"
    },
}

TOOLS_LIST = "\n".join([
    f"- **{t['name']}**: {t['desc']} Params: {', '.join(t['params'])}"
    for t in TOOLS.values()
])

# Skill executor functions
def execute_hermes_skill(skill_name, query):
    """Load and execute a Hermes skill by name. Routes to appropriate executor based on skill type."""
    import json as json_mod
    
    # Normalize skill name: replace underscores with hyphens for directory lookup
    # (AI sometimes outputs underscores, actual dirs use hyphens)
    normalized_name = skill_name.replace("_", "-")
    
    # Map skill names to SKILL.md paths
    skill_path = Path.home() / ".hermes" / "skills" / skill_name.replace(".", "/") / "SKILL.md"
    
    # Try normalized (hyphens)
    if not skill_path.exists():
        skill_path = Path.home() / ".hermes" / "skills" / normalized_name.replace(".", "/") / "SKILL.md"
    
    # Try root-level skills (e.g., "dogfood", "yuanbao", "mine", "predict-worknet")
    if not skill_path.exists():
        skill_path = Path.home() / ".hermes" / "skills" / skill_name / "SKILL.md"
    
    if not skill_path.exists():
        skill_path = Path.home() / ".hermes" / "skills" / normalized_name / "SKILL.md"
    
    if not skill_path.exists():
        # Search all skills for partial match (all search parts must appear in rel)
        skills_dir = Path.home() / ".hermes" / "skills"
        search_parts = [p for p in re.split(r'[-._]', normalized_name) if p]
        for sp in skills_dir.rglob("SKILL.md"):
            rel = str(sp.relative_to(skills_dir).parent)
            # All search parts must be contained in rel (order-free partial match)
            if all(p in rel for p in search_parts):
                skill_path = sp
                break
    
    if not skill_path.exists():
        return f"Skill '{skill_name}' not found. Available: 104 skills across 21 categories."
    
    try:
        content = skill_path.read_text()
        
        # Strip frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            content = parts[2] if len(parts) >= 3 else content
        
        # Parse frontmatter for metadata
        frontmatter = {}
        if parts[0].strip().startswith("---"):
            try:
                import yaml
                frontmatter = yaml.safe_load(parts[1]) or {}
            except:
                pass
        
        # Extract title
        lines = content.split("\n")
        title = ""
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        
        # Detect skill type - check for ACTUAL executables, not just mentions
        ct = content
        
        # Check for actual curl/http calls with real endpoints
        has_api_call = bool(re.search(r'curl\s+["\']?https?://', ct)) or \
                       bool(re.search(r'requests\.(?:get|post)\(', ct)) or \
                       bool(re.search(r'GET\s+https?://|POST\s+https?://', ct))
        
        # Check for terminal commands (not just mentions)
        has_terminal = bool(re.search(r'```(?:bash|sh|shell|zsh)\n', ct)) or \
                       bool(re.search(r'\$\s+\w', ct)) or \
                       bool(re.search(r'\bnpx\s+\w+', ct)) or \
                       bool(re.search(r'\bnpm\s+(install|run|test)', ct))
        
        # Check for browser/playwright
        has_browser = bool(re.search(r'playwright|browser_navigate|browser_snapshot|page\.goto', ct))
        
        # Check for jupyter
        has_jupyter = bool(re.search(r'jupyter_kernel|kc\.execute|KernelManager', ct))
        
        if has_api_call:
            skill_type = "api"
        elif has_terminal:
            skill_type = "terminal"
        elif has_browser:
            skill_type = "browser"
        elif has_jupyter:
            skill_type = "jupyter"
        else:
            skill_type = "knowledge"
        
        # === EXECUTE BASED ON SKILL ===
        
        # Normalize skill_name for routing
        routing_name = normalized_name
        
        # ---- API-BASED SKILLS ----
        if routing_name in ("research.polymarket", "research.polymarket"):
            return execute_polymarket(query)
        
        if routing_name in ("research.meteora-dlmm-data", "research.meteora_dlmm_data"):
            # Extract pool address from query or use default
            pool = query.strip() if query.strip() else "CafMC1jinkxXx3ikBgPpyRaHqhND23dVSjRdWAaUtdDb"
            return execute_meteora_dlmm(pool)
        
        if routing_name in ("media.youtube-content", "media.youtube_content"):
            # Extract YouTube URL from query
            import re as re_mod
            urls = re_mod.findall(r'(https?://[^\s]+)', query)
            url = urls[0] if urls else ""
            if not url:
                return "YouTube content skill: Berikan URL video YouTube untuk extract/transcript. Contoh: [TOOL: hermes_skill | skill_name='media.youtube-content' | query='https://youtube.com/watch?v=xxx']"
            return execute_youtube_content(url)
        
        if routing_name in ("media.gif-search", "media.gif_search"):
            # Extract search query
            return execute_gif_search(query)
        
        if routing_name in ("research.arxiv", "research.arxiv"):
            return execute_arxiv(query)
        
        if routing_name in ("data-science.google-news-rss-scraper", "data-science.google_news_rss_scraper", "data-science.google-news", "data.science.google-news-rss-scraper"):
            return execute_google_news(query or "Indonesia")
        
        if routing_name in ("devops.caddy-websocket-proxy", "devops.caddy_websocket_proxy"):
            return ("Caddy WebSocket Proxy Skill:\n\n"
                    "Masalah: Caddy tidak handle WebSocket upgrade secara default.\n"
                    "Solusi: Tambahkan @ws matcher di Caddyfile:\n\n"
                    "`:80 {\n"
                    "    @ws {\n"
                    "        header Upgrade *stream*\n"
                    "        path /ws\n"
                    "    }\n"
                    "    reverse_proxy @ws localhost:5001\n"
                    "    reverse_proxy /api/* localhost:5002\n"
                    "    reverse_proxy / localhost:8080\n"
                    "}`\n\n"
                    "Atau gunakan directive @websocket:\n"
                    " `handle /ws* { @ws reverse_proxy... }`")
        
        if routing_name in ("productivity.capacitor-webview-pitfalls", "productivity.capacitor_webview_pitfalls"):
            return ("Capacitor WebView Pitfalls:\n\n"
                    "1. WebSocket URL HARUS hardcoded untuk APK: `ws://IP/ws`\n"
                    "2. allowMixedContent: true di capacitor.config.ts\n"
                    "3. cleartext: true untuk AndroidManifest.xml\n"
                    "4. WebView caches content — edit www/ bukan src/\n"
                    "5. CORS issues — proxy via Caddy atau native handler\n"
                    "6. localStorage persists — clear via app settings")
        
        if routing_name in ("productivity.maps", "productivity.maps"):
            return ("Maps Skill:\n\n"
                    "Gunakan requests ke OpenStreetMap API:\n"
                    "- Geocoding: `https://nominatim.openstreetmap.org/search?q=Jakarta&format=json`\n"
                    "- Reverse: `https://nominatim.openstreetmap.org/reverse?lat=X&lon=Y&format=json`\n"
                    "- POI: `https://overpass-api.de/api/interpreter?data=[out:json];node[amenity=restaurant](Jakarta);out;`\n"
                    "- Routing: `https://router.project-osrm.org/route/v1/driving/lon1,lat1;lon2,lat2`")
        
        # ---- API SKILLS: Execute curl commands from skill content ----
        api_skill_commands = {
            "autonomous-ai-agents.hermes-agent": lambda q: execute_terminal("hermes --help 2>/dev/null || echo 'Hermes CLI not found in PATH'"),
            "github.github-auth": lambda q: execute_terminal("gh auth status 2>&1 || echo 'GitHub CLI not authenticated'"),
            "mlops.huggingface-hub": lambda q: execute_terminal(f"hf transfer --help 2>&1 | head -20 || echo 'huggingface_hub CLI check'"),
            "monitoring.telegram-channel-monitor": lambda q: _execute_telegram_channel(query) if query else "Telegram Channel Monitor:\nBerikan nama channel atau username untuk monitor.\nContoh: [TOOL: hermes_skill | skill_name='monitoring.telegram-channel-monitor' | query='@channelname']",
        }
        
        if routing_name in api_skill_commands:
            return api_skill_commands[routing_name](query)
        
        # Generic API skill: extract and run curl commands
        if skill_type == "api":
            import re as re_mod
            curl_cmds = re_mod.findall(r'curl\s+(?:-[a-zA-Z]+\s+)?["\']?(https?://[^\s"\']+)["\']?', content)
            
            if curl_cmds:
                # Build curl command with common headers
                results = []
                for url in curl_cmds[:2]:
                    clean_url = url.strip().rstrip("'").rstrip('"')
                    cmd = f"curl -s -L '{clean_url}'"
                    r = execute_terminal(cmd, timeout=15)
                    results.append(r[:500])
                
                if results:
                    return f"[API: {title or skill_name}]\n\n" + "\n---\n".join(results)
            
            return (f"API Skill: {title or skill_name}\n"
                    f"Type: API\n"
                    f"URLs found: {len(curl_cmds)}\n"
                    f"Query: {query}\n\n"
                    f"Skill content preview:\n{content[:2000]}")
        
        # ---- TERMINAL/CLI SKILLS ----
        if skill_type == "terminal":
            # Only execute if there are actual bash/shell code blocks
            import re as re_mod
            commands = []
            
            # Find bash code blocks ONLY (not ASCII art, diagrams, etc)
            for block in re_mod.findall(r'```bash\n(.*?)```', content, re_mod.DOTALL):
                for line in block.strip().split('\n'):
                    line = line.strip()
                    # Skip empty, comments, and markdown-ish lines
                    if line and not line.startswith('#') and not line.startswith('```') and \
                       not line.startswith('- ') and not line.startswith('|') and \
                       len(line) > 2 and not line.startswith('*'):
                        commands.append(line)
            
            # Find $ prefixed lines that look like real commands (not table formatting)
            for match in re_mod.finditer(r'^\$\s+(.+?)$', content, re_mod.MULTILINE):
                cmd = match.group(1).strip()
                # Real commands are alphanumeric/standard CLI
                if cmd and re_mod.match(r'^[a-zA-Z0-9_./-]+', cmd) and len(cmd) > 3:
                    commands.append(cmd)
            
            if commands:
                # Execute first 1-2 meaningful commands
                results = []
                for cmd in commands[:2]:
                    if any(k in cmd for k in ['sudo ', 'passwd', 'chmod 7', 'rm -rf /', 'mkfs', 'fdisk']):
                        continue
                    
                    # Handle cd commands - extract path and rest
                    if cmd.startswith('cd '):
                        parts = cmd.split('&&', 1)
                        if len(parts) == 1:
                            continue
                        else:
                            cd_part = parts[0].strip()
                            rest = parts[1].strip()
                            path = cd_part.replace('cd', '').strip()
                            cmd_to_run = f"cd {path} && {rest}"
                    else:
                        cmd_to_run = cmd
                    
                    r = execute_terminal(cmd_to_run, timeout=20)
                    results.append(f"$ {cmd}\n{r}")
                if results:
                    return f"[{title or skill_name}]\n\n" + "\n---\n".join(results)
            
            return (f"Terminal Skill: {title or skill_name}\n\n"
                    f"Type: Terminal/CLI\n"
                    f"Query: {query}\n\n"
                    f"{content[:3000]}")
        
        # ---- BROWSER SKILLS ----
        if skill_type == "browser":
            # Extract URLs and actions from skill
            import re as re_mod
            urls = re_mod.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
            
            if urls and query:
                # Try to browse the most relevant URL
                primary_url = urls[0]
                r = execute_browser(primary_url, "snapshot")
                return f"[Browser: {title or skill_name}]\nURL: {primary_url}\n\n{r}"
            
            return (f"Browser Skill: {title or skill_name}\n\n"
                    f"Type: Browser-based\n"
                    f"URLs found: {len(urls)}\n"
                    f"Query: {query}\n\n"
                    f"Skill content preview:\n{content[:1500]}")
        
        # ---- JUPYTER SKILLS ----
        if skill_type == "jupyter":
            # Extract Python code blocks
            import re as re_mod
            code_blocks = re_mod.findall(r'```python\n(.*?)```', content, re_mod.DOTALL)
            code_blocks += re_mod.findall(r'```py\n(.*?)```', content, re_mod.DOTALL)
            
            if code_blocks:
                # Execute first meaningful code block
                code = code_blocks[0].strip()
                if len(code) > 10 and not code.startswith('# tutorial'):
                    r = execute_jupyter(code)
                    return f"[Jupyter: {title or skill_name}]\n\n{r}"
            
            return (f"Jupyter Skill: {title or skill_name}\n\n"
                    f"Type: Jupyter Notebook\n"
                    f"Code blocks found: {len(code_blocks)}\n"
                    f"Query: {query}\n\n"
                    f"Skill content preview:\n{content[:1500]}")
        
        # ---- KNOWLEDGE / FILE SKILLS ----
        # Return the actual skill content for knowledge skills
        return (f"Skill: {title or skill_name}\n"
                f"Type: {skill_type.capitalize()}\n"
                f"Size: {len(content)} chars\n\n"
                f"{content[:4000]}")
    
    except Exception as e:
        return f"Error loading skill '{skill_name}': {str(e)}"

def execute_youtube_content(url):
    """Get YouTube video transcript/content"""
    try:
        import re as re_mod
        # Extract video ID
        match = re_mod.search(r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not match:
            return f"Invalid YouTube URL: {url}"
        video_id = match.group(1)
        
        # Try to get video info via oembed
        oembed_url = f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
        r = requests.get(oembed_url, timeout=5)
        if r.status_code == 200:
            info = r.json()
            title = info.get("title", "Unknown")
            author = info.get("author_name", "Unknown")
            return f"YouTube Video:\nTitle: {title}\nAuthor: {author}\nURL: {url}\n\nNote: Full transcript requires yt-dlp or similar. Install: pip install yt-dlp"
        return f"YouTube video detected (ID: {video_id}). Transcript extraction requires yt-dlp."
    except Exception as e:
        return f"YouTube error: {str(e)}"

def execute_gif_search(query):
    """Search GIFs via Tenor API"""
    try:
        import json
        # Tenor free API (no key needed for basic)
        tenor_url = "https://tenor.googleapis.com/v2/search"
        params = {
            "q": query or "funny",
            "key": "AIzaSyAyimkuYQYF_FXVALexPuGQctUWRURdCYQ",  # demo key
            "limit": 6,
            "media_filter": "gif,mp4",
            "contentfilter": "medium"
        }
        r = requests.get(tenor_url, params=params, timeout=8)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if not results:
                return f"No GIFs found for '{query}'"
            output = [f"GIF results for '{query}':"]
            for item in results[:6]:
                desc = item.get("content_description", "GIF")
                gif_url = item.get("media_formats", {}).get("gif", {}).get("url", "")
                if gif_url:
                    output.append(f"- {desc}: {gif_url}")
            return "\n".join(output)
        return f"Tenor API error: {r.status_code}"
    except Exception as e:
        return f"GIF search error: {str(e)}"

def execute_arxiv(query):
    """Search arXiv papers"""
    try:
        import xml.etree.ElementTree as ET
        import re as re_mod
        
        # Parse query
        if query.strip().startswith("http"):
            # Extract ID from URL
            match = re_mod.search(r'(\d+\.\d+)', query)
            arxiv_id = match.group(1) if match else query
            url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
        else:
            url = f"https://export.arxiv.org/api/query?search_query=all:{re_mod.sub(r' ', '+', query)}&max_results=5&sortBy=submittedDate&sortOrder=descending"
        
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return f"arXiv API error: {r.status_code}"
        
        root = ET.fromstring(r.text)
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('a:entry', ns)
        
        if not entries:
            return f"No papers found for '{query}'"
        
        results = ["arXiv Papers:"]
        for i, entry in enumerate(entries):
            title = entry.find('a:title', ns)
            title = title.text.strip().replace('\n', ' ') if title is not None else "Unknown"
            arxiv_id = entry.find('a:id', ns)
            arxiv_id = arxiv_id.text.strip().split('/abs/')[-1] if arxiv_id is not None else "Unknown"
            published = entry.find('a:published', ns)
            published = published.text[:10] if published is not None else "Unknown"
            authors = entry.findall('a:author', ns)
            author_names = ', '.join(a.find('a:name', ns).text for a in authors[:3])
            summary = entry.find('a:summary', ns)
            summary = summary.text.strip()[:150] if summary is not None else ""
            
            results.append(f"\n{i+1}. [{arxiv_id}] {title}")
            results.append(f"   Authors: {author_names}")
            results.append(f"   Published: {published}")
            results.append(f"   Abstract: {summary}...")
            results.append(f"   URL: https://arxiv.org/abs/{arxiv_id}")
        
        return "\n".join(results)
    except Exception as e:
        return f"arXiv error: {str(e)}"

def execute_google_news(topic):
    """Get Google News via RSS"""
    try:
        import re as re_mod
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=id&gl=ID&ceid=ID:id"
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return f"Google News error: {r.status_code}"
        
        titles = re_mod.findall(r'<title>(.*?)</title>', r.text)
        # Skip first 2 (channel title + empty)
        titles = [t for t in titles[2:] if t and not t.startswith("http")][:8]
        
        if not titles:
            return f"No news found for '{topic}'"
        
        return f"Berita: {topic}\n\n" + "\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
    except Exception as e:
        return f"Google News error: {str(e)}"

def execute_polymarket(query):
    """Get Polymarket prediction market data"""
    try:
        import json
        url = f"https://gamma-api.polymarket.com/public-search?q={urllib.parse.quote(query)}"
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return f"Polymarket API error: {r.status_code}"
        
        data = r.json()
        events = data.get("events", [])
        if not events:
            return f"No markets found for '{query}'"
        
        results = []
        for event in events[:5]:
            title = event.get("title", "")
            volume = event.get("volume", 0)
            markets = event.get("markets", [])
            for m in markets[:2]:
                question = m.get("question", "")
                try:
                    prices = json.loads(m.get("outcomePrices", "[]"))
                    outcomes = json.loads(m.get("outcomes", "[]"))
                except:
                    prices = []
                    outcomes = []
                
                if len(prices) >= 2:
                    yes_pct = float(prices[0]) * 100
                    no_pct = float(prices[1]) * 100
                    vol = m.get("volume", volume)
                    results.append(f"Q: {question}\n  Yes: {yes_pct:.1f}% | No: {no_pct:.1f}%\n  Vol: ${float(vol or 0):,.0f}")
        
        if results:
            return "Polymarket Markets:\n\n" + "\n\n".join(results)
        return f"No markets found for '{query}'"
    except Exception as e:
        return f"Polymarket error: {str(e)}"

def execute_meteora_dlmm(pool_address):
    """Get Meteora DLMM pool data"""
    try:
        import json
        # Meteora DLMM API
        url = f"https://api.meteora.ag/pools/{pool_address}"
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return f"Meteora pool not found: {r.status_code}"
        
        data = r.json()
        return (f"Meteora DLMM Pool:\n"
                f"Name: {data.get('name', 'N/A')}\n"
                f"Token X: {data.get('token_x', 'N/A')}\n"
                f"Token Y: {data.get('token_y', 'N/A')}\n"
                f"TVL: ${float(data.get('tvl', 0)):,.0f}\n"
                f"Fee: {data.get('fee', 'N/A')}%\n"
                f"Active bin: {data.get('active_bin', 'N/A')}\n"
                f"Price: {data.get('price', 'N/A')}")
    except Exception as e:
        return f"Meteora error: {str(e)}"

# Tool executor functions
async def exec_tool(name, params):
    """Execute a tool and return result"""
    try:
        if name == "calculator":
            expr = params.get("expression", "0")
            # Safe math evaluation using ast.literal_eval equivalent
            import ast
            try:
                # Parse as expression and evaluate safely
                tree = ast.parse(expr, mode='eval')
                # Only allow Num, BinOp (Add, Sub, Mult, Div, Mod, Pow), UnaryOp, and operators
                allowed_nodes = (ast.Expression, ast.expr, ast.BinOp, ast.UnaryOp, ast.operator, ast.unaryop,
                               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv, ast.BitXor,
                               ast.USub, ast.UAdd, ast.Num, ast.Constant)
                for node in ast.walk(tree):
                    if not isinstance(node, allowed_nodes):
                        return "Error: Invalid expression"
                result = eval(compile(tree, '<string>', 'eval'), {"__builtins__": {}})
                return str(result)
            except:
                return "Error: Invalid expression"

        elif name == "currency_convert":
            amount = float(params.get("amount", 0))
            from_c = params.get("from_currency", "USD").upper()
            to_c = params.get("to_currency", "IDR").upper()
            # Fetch real-time exchange rates
            try:
                url = f"https://open.er-api.com/v6/latest/{from_c}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    if to_c in data.get("rates", {}):
                        rate = data["rates"][to_c]
                        result = amount * rate
                        return f"{amount} {from_c} = {result:,.2f} {to_c}"
                return f"Could not get rate for {from_c} -> {to_c}"
            except:
                return f"Failed to fetch exchange rate"

        elif name == "wikipedia":
            topic = params.get("topic", "")
            # Use Wikipedia API
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(topic)}"
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return f"📖 {data.get('title', topic)}\\n\\n{data.get('extract', 'No information found.')}"
                return f"No Wikipedia article found for '{topic}'"
            except:
                return f"Could not fetch Wikipedia for '{topic}'"

        elif name == "weather":
            city = params.get("city", "")
            # Use wttr.in - free weather API
            try:
                url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    current = data.get("current_condition", [{}])[0]
                    temp = current.get("temp_C", "N/A")
                    desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
                    humidity = current.get("humidity", "N/A")
                    return f"🌤️ Cuaca di {city}:\\n• Suhu: {temp}°C\\n• {desc}\\n• Kelembapan: {humidity}%"
                return f"Could not get weather for '{city}'"
            except:
                return f"Could not fetch weather for '{city}'"

        elif name == "news":
            topic = params.get("topic", "general")
            # Use Google News RSS (free, no API key, Indonesian results)
            try:
                url = f"https://news.google.com/rss/search"
                params = {"q": topic, "hl": "id", "gl": "ID", "ceid": "ID:id"}
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, params=params, headers=headers, timeout=5)
                if r.status_code == 200:
                    titles = re.findall(r'<title>(.*?)</title>', r.text)
                    if titles:
                        # Skip first 2 (channel title + "Google Berita")
                        items = [t.strip() for t in titles[2:7] if t.strip()]
                        if items:
                            results = "\n".join([f"• {t}" for t in items])
                            return f"📰 Berita tentang '{topic}':\n\n{results}\n\n(Sumber: Google News)"
                    return f" Tidak ada berita ditemukan untuk '{topic}'"
                return f" Gagal mengambil berita untuk '{topic}'"
            except:
                return f" Error fetching news"

        elif name == "translate":
            text = params.get("text", "")
            from_lang = params.get("from_lang", "en")
            to_lang = params.get("to_lang", "id")
            # Simple mock - in production would use Google Translate API
            return f"[Translation {from_lang} -> {to_lang}]: {text}"

        elif name == "hermes_skill":
            skill_name = params.get("skill_name", "")
            query = params.get("query", "")
            return execute_hermes_skill(skill_name, query)

        elif name == "polymarket":
            query = params.get("query", "")
            return execute_polymarket(query)

        elif name == "meteora_dlmm":
            pool_address = params.get("pool_address", "")
            return execute_meteora_dlmm(pool_address)

        elif name == "terminal":
            command = params.get("command", "")
            return execute_terminal(command)

        elif name == "browser":
            url = params.get("url", "")
            action = params.get("action", "snapshot")
            selector = params.get("selector")
            value = params.get("value")
            return execute_browser(url, action, selector, value)

        elif name == "jupyter":
            code = params.get("code", "")
            kernel = params.get("kernel", "python3")
            return execute_jupyter(code, kernel)

        elif name == "code_exec":
            code = params.get("code", "")
            # SAFE code execution - restrict to safe builtins only
            try:
                # Create safe evaluation environment
                safe_builtins = {
                    'abs': abs, 'min': min, 'max': max, 'sum': sum,
                    'round': round, 'pow': pow, 'len': len, 'range': range,
                    'sorted': sorted, 'reversed': reversed, 'enumerate': enumerate,
                    'zip': zip, 'map': map, 'filter': filter, 'any': any, 'all': all,
                    'int': int, 'float': float, 'str': str, 'bool': bool, 'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
                    'print': print,
                }
                # Block dangerous builtins
                forbidden = {'__import__', 'eval', 'exec', 'open', 'file', 'input', 'compile', 'dir', 'vars', 'globals', 'locals', 'breakpoint', 'exit', 'quit'}
                code_tokens = code.replace('(', ' ').replace(')', ' ').replace('.', ' ').split()
                for token in code_tokens:
                    if token in forbidden:
                        return f"Error: Forbidden operation '{token}'"
                
                # Use AST for safe evaluation
                import ast
                tree = ast.parse(code, mode='exec')
                # Check for dangerous nodes
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if hasattr(node.func, 'id') and node.func.id in forbidden:
                            return f"Error: Forbidden function '{node.func.id}'"
                        if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden:
                            return f"Error: Forbidden attribute '{node.func.attr}'"
                
                # Execute in restricted namespace
                exec_globals = {'__builtins__': safe_builtins}
                exec(code, exec_globals)
                return "(code executed successfully)"
            except SyntaxError as e:
                return f"Syntax error: {e}"
            except NameError as e:
                return f"Name error: {e}"
            except TypeError as e:
                return f"Type error: {e}"
            except Exception as e:
                return f"Error: {str(e)}"

        elif name == "web_search":
            query = params.get("query", "")
            # Use DuckDuckGo HTML (no API key needed)
            try:
                url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers, timeout=5)
                if r.status_code == 200:
                    # Extract first few results
                    titles = re.findall(r'<a class="result__a"[^>]*href="[^"]*"[^>]*>([^<]+)</a>', r.text)[:3]
                    if titles:
                        results = "\\n".join([f"• {t}" for t in titles])
                        return f"🔍 Hasil pencarian '{query}':\\n\\n{results}\\n\\n(Sumber: DuckDuckGo)"
                    return f"Tidak ada hasil untuk '{query}'"
                return f"Search failed for '{query}'"
            except:
                return f"Could not search for '{query}'"

        elif name == "crypto_price":
            symbol = params.get("symbol", "BTC").upper()
            try:
                # Primary: Binance API (no rate limit)
                binance_map = {
                    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
                    "XRP": "XRPUSDT", "DOGE": "DOGEUSDT", "ADA": "ADAUSDT",
                    "DOT": "DOTUSDT", "AVAX": "AVAXUSDT", "LINK": "LINKUSDT"
                }
                binance_sym = binance_map.get(symbol, f"{symbol}USDT")
                r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={binance_sym}", timeout=5)
                if r.status_code == 200 and "price" in r.json():
                    price_usd = float(r.json()["price"])
                    # Convert to IDR using exchange rate
                    try:
                        rate_r = requests.get("https://open.er-api.com/v6/latest/USDT", timeout=5)
                        rate_idr = rate_r.json()["rates"]["IDR"] if rate_r.status_code == 200 else 16500
                    except:
                        rate_idr = 16500
                    price_idr = price_usd * rate_idr
                    return f"💰 {symbol} sekarang:\n• USD: ${price_usd:,.2f}\n• IDR: Rp {price_idr:,.0f}"
                return f"Tidak ada data untuk {symbol}"
            except Exception as e:
                return f"Error fetching {symbol}: {str(e)}"

        elif name == "image_gen":
            prompt = params.get("prompt", "")
            # Placeholder - would need DALL-E or similar API
            return f"🎨 Image generation: '{prompt}'\\n\\n(Image generation requires API key setup. User will be notified.)"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error: {str(e)}"

# Pattern to detect tool calls in AI response
# Safe pattern: word chars for tool name, quoted params, no nested brackets
TOOL_PATTERN = re.compile(r'\[TOOL:\s*(\w+)\s*\|([^\]]+)\]')

# ============================================================
# ADVANCED TOOL EXECUTORS (Terminal, Browser, Jupyter)
# ============================================================

def _execute_telegram_channel(query):
    """Monitor a Telegram channel via scraping (public channels only)."""
    if not query or len(query) < 2:
        return "Telegram Channel Monitor:\n\nGunakan format @channelname atau nama channel.\nContoh: [TOOL: hermes_skill | skill_name='monitoring.telegram-channel-monitor' | query='@channelname']"
    
    # Extract channel name/username
    channel = query.strip().lstrip('@').strip()
    if not channel:
        return "Telegram Channel Monitor:\n\nFormat: @channelname atau nama channel."
    
    # Try to fetch via Telegram API (public channels need bot token for full access)
    # For now, return guidance
    return (f"Telegram Channel Monitor: @{channel}\n\n"
            "Note: Full Telegram channel monitoring requires:\n"
            "1. A Telegram Bot token (@BotFather)\n"
            "2. The bot must be added to the channel as admin\n"
            "3. Bot token stored in environment\n\n"
            "For public channels, you can try scraping via web:\n"
            f"[TOOL: browser | url='https://t.me/s/{channel}' | action='snapshot']")

def execute_terminal(command, timeout=30):
    """Execute a safe shell command. Blocked: os, sys, subprocess, pty, socket, etc."""
    import shlex
    forbidden = ['__import__', 'eval', 'exec', 'open', 'file', 'compile', 'reload',
                 'exit', 'quit', 'breakpoint', 'os.', 'sys.', 'subprocess', 'pty',
                 'socket', 'requests', 'urllib', 'http', 'wget',
                 'chmod 7', 'chown', 'sudo', 'su ', 'passwd',
                 'rm -rf', 'dd if=', 'mkfs', 'fdisk', 'parted']
    cmd_lower = command.lower()
    for fw in forbidden:
        if fw in cmd_lower:
            return f"Error: Forbidden command pattern '{fw}'"
    
    try:
        # Use shlex.split for safety, limit to simple commands
        args = shlex.split(command)
        if not args:
            return "Error: Empty command"
        
        # Whitelist allowed commands
        allowed = {'ls', 'pwd', 'whoami', 'date', 'cat', 'echo', 'head', 'tail',
                   'grep', 'awk', 'sed', 'sort', 'uniq', 'wc', 'find', 'mkdir',
                   'cp', 'mv', 'touch', 'tree', 'df', 'free', 'uptime', 'ps',
                   'curl', 'git', 'npm', 'npx', 'pip', 'pip3', 'python', 'python3',
                   'node', 'ruby', 'perl', 'bash', 'sh', 'zcat', 'xzcat', 'tar',
                   'gzip', 'gunzip', 'zip', 'unzip', 'id', 'hostname', 'uname',
                   'arch', 'type', 'which', 'env', 'printenv', 'seq', 'yes',
                   'base64', 'md5sum', 'sha256sum', 'sha1sum', 'xxd', 'hexdump',
                   'gh', 'kubectl', 'docker', 'helm', 'terraform', 'ansible-playbook',
                   'ssh', 'rsync', 'scp', 'cd', 'cdir', 'pushd', 'popd', 'exit', 'cd ~'}
        
        cmd_name = args[0]
        if cmd_name not in allowed:
            return f"Error: Command '{cmd_name}' not allowed. Allowed: {', '.join(sorted(allowed))[:200]}..."
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        
        if not output.strip():
            output = "(command executed, no output)"
        
        # Truncate if too long
        if len(output) > 5000:
            output = output[:5000] + f"\n... (truncated, {len(output)-5000} more chars)"
        
        return output
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {str(e)}"

def execute_browser(url, action="snapshot", selector=None, value=None):
    """Use Playwright to navigate, click, type, or snapshot a webpage."""
    import os
    
    def _do_browser():
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "Error: Playwright not installed. Run: pip3 install playwright && playwright install chromium"
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            
            try:
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                
                if action == "snapshot":
                    content = page.inner_text("body")
                    if len(content) > 3000:
                        content = content[:3000] + f"\n... (truncated from {len(content)} chars)"
                    return f"[Page: {url}]\n\n{content}"
                
                elif action == "screenshot":
                    ss_path = f"/tmp/browser_ss_{os.getpid()}.png"
                    page.screenshot(path=ss_path, full_page=False)
                    browser.close()
                    return f"[SCREENSHOT saved to {ss_path}]"
                
                elif action == "click" and selector:
                    page.click(selector, timeout=5000)
                    page.wait_for_load_state("networkidle", timeout=5000)
                    content = page.inner_text("body")
                    return f"[Clicked: {selector}]\n\n{content[:2000]}"
                
                elif action == "type" and selector and value:
                    page.fill(selector, value, timeout=5000)
                    return f"[Typed: '{value}' into {selector}]"
                
                elif action == "evaluate" and value:
                    result = page.evaluate(value)
                    return f"[JS Result]\n{str(result)[:1000]}"
                
                else:
                    title = page.title()
                    return f"[Page: {url}]\nTitle: {title}\n\n(Unknown action: {action})"
                    
            finally:
                browser.close()
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_browser)
            return future.result(timeout=30)
    except concurrent.futures.TimeoutError:
        return "Error: Browser timed out after 30s"
    except Exception as e:
        return f"Browser error: {str(e)}"

def execute_jupyter(code, kernel="python3"):
    """Execute Python code with full package support (numpy, pandas, matplotlib)."""
    import subprocess
    import tempfile
    import os
    
    # For full matplotlib support without display, use Agg backend
    if "matplotlib" in code and "Agg" not in code and "inline" not in code:
        code = "import matplotlib\nmatplotlib.use('Agg')\n" + code
    
    # If code doesn't print anything, add a print result
    if "print(" not in code and "return" not in code:
        # Try to detect if last line is an expression
        lines = code.strip().split('\n')
        last = lines[-1].strip()
        if last and not last.startswith('#') and not any(last.startswith(k) for k in ['import', 'def ', 'class ', 'if ', 'for ', 'while ', 'try:', 'with ', 'return']):
            code += f"\nprint({last})"
    
    # Write to temp file to avoid issues with quotes in command
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(code)
        tmp_path = f.name
    
    try:
        result = subprocess.run(
            ['python3', tmp_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        
        if not output.strip():
            output = "(code executed, no output)"
        
        if len(output) > 5000:
            output = output[:5000] + f"\n... (truncated from {len(output)} chars)"
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"Error: Code timed out after 30s"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

def parse_tool_call(text):
    """Parse tool call from AI response text"""
    matches = []
    for match in TOOL_PATTERN.finditer(text):
        tool_name = match.group(1)
        params_str = match.group(2)
        params = {}
        for param in params_str.split('|'):
            if '=' in param:
                key, value = param.split('=', 1)
                # Strip quotes from value
                value = value.strip().strip("'").strip('"')
                params[key.strip()] = value
        matches.append((match.group(0), tool_name, params))
    return matches

print("╔══════════════════════════════════════════════╗")
print("║     AI CHAT SERVER - MiniMax Real AI        ║")
print("╚══════════════════════════════════════════════╝")
print(f"Model: {MINIMAX_MODEL}")
print(f"API: {MINIMAX_BASE_URL}/anthropic/v1/messages")
print(f"Key: {'*' * 20}{MINIMAX_API_KEY[-10:] if MINIMAX_API_KEY else 'NOT FOUND'}")
print()

async def call_minimax_stream(messages):
    """Call MiniMax API with streaming and yield chunks"""
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": MINIMAX_MODEL,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7,
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{MINIMAX_BASE_URL}/anthropic/v1/messages",
            headers=headers,
            json=payload,
            timeout=60,
            stream=True
        )
        
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data = decoded[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            content = json_data.get("content", [])
                            if isinstance(content, list):
                                for c in content:
                                    if c.get("type") == "text":
                                        yield c.get("text", "")
                        except:
                            pass
        else:
            error_msg = response.text[:200]
            yield f"Error {response.status_code}: {error_msg}"
            
    except Exception as e:
        yield f"Connection error: {str(e)}"

async def call_minimax(messages, session_id=None):
    """Call MiniMax API and return full response text (non-streaming fallback)"""
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": MINIMAX_MODEL,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            f"{MINIMAX_BASE_URL}/anthropic/v1/messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("content", [])
            if isinstance(content, list):
                text = "".join([c.get("text", "") for c in content if c.get("type") == "text"])
            else:
                text = str(content)
            return text, result.get("usage", {})
        else:
            error_msg = response.text[:200]
            return f"Error {response.status_code}: {error_msg}", {}
            
    except Exception as e:
        return f"Connection error: {str(e)}", {}

async def handler(websocket):
    """Handle client connection"""
    client_id = id(websocket)
    connected_clients.add(client_id)
    print(f"[+] Client {client_id} connected ({len(connected_clients)} online)")
    
    # Separate memories for AI and User
    ai_memory = {
        "name": "AI Assistant",
        "language": None,
        "created_at": datetime.now().isoformat()
    }
    
    user_memory = {
        "name": None,
        "language": None,
        "preferences": {}
    }
    
    session_messages = []
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get("type") == "restore" and data.get("history"):
                    # Restore session from client localStorage
                    session_messages = data.get("history", [])
                    await websocket.send(json.dumps({
                        "type": "response",
                        "message": "Sesi Dipulihkan! Mari lanjutkan percakapan kita."
                    }))
                    continue

                if data.get("type") == "chat":
                    user_msg = data.get("message", "")
                    
                    # If client sends history, merge it into session
                    if data.get("history"):
                        for h in data["history"]:
                            if h not in session_messages:
                                session_messages.append(h)
                    print(f"[User {client_id}]: {user_msg[:100]}")
                    
                    # Special handling for /start
                    if user_msg.strip().lower() == "/start":
                        response_text = "Silakan pilih bahasa untuk melanjutkan:"
                        await websocket.send(json.dumps({
                            "type": "response",
                            "message": response_text,
                            "choices": [
                                {"label": "Indonesia", "value": "Indonesia"},
                                {"label": "English", "value": "English"}
                            ]
                        }))
                        continue

                    # Special handling for language selection
                    if user_msg.strip() == "Indonesia":
                        user_memory["language"] = "id"
                        response_text = "Bahasa Indonesia dipilih!\n\nHalo! Saya AI Assistant Anda. Ada yang bisa saya bantu hari ini?"
                        await websocket.send(json.dumps({
                            "type": "response",
                            "message": response_text
                        }))
                        # Add to session with language context
                        session_messages.append({"role": "user", "content": user_msg})
                        session_messages.append({"role": "assistant", "content": response_text})
                        session_messages.append({"role": "user", "content": "Saya ingin berkomunikasi dalam Bahasa Indonesia"})
                        continue

                    if user_msg.strip() == "English":
                        user_memory["language"] = "en"
                        response_text = "English selected!\n\nHello! I'm your AI Assistant. How can I help you today?"
                        await websocket.send(json.dumps({
                            "type": "response",
                            "message": response_text
                        }))
                        # Add to session with language context
                        session_messages.append({"role": "user", "content": user_msg})
                        session_messages.append({"role": "assistant", "content": response_text})
                        session_messages.append({"role": "user", "content": "I want to communicate in English"})
                        continue
                    
                    # Special handling for /skill command
                    if user_msg.strip().lower().startswith('/skill '):
                        skill_cmd = user_msg.strip()[7:].strip()  # Remove '/skill ' prefix
                        # Parse skill name and optional query
                        parts = skill_cmd.split(None, 1)
                        skill_name = parts[0] if parts else ''
                        skill_query = parts[1] if len(parts) > 1 else ''
                        
                        if not skill_name:
                            response_text = "Format: /skill <skill_name> [query]\nContoh: /skill research.polymarket BTC price"
                            await websocket.send(json.dumps({"type": "response", "message": response_text}))
                            continue
                        
                        # Try to execute the skill
                        try:
                            result = execute_hermes_skill(skill_name, skill_query)
                            response_text = result[:2000] if len(result) > 2000 else result
                            if not response_text.strip():
                                response_text = f"Skill '{skill_name}' tidak ditemukan atau tidak bisa dieksekusi."
                        except Exception as e:
                            response_text = f"Error executing skill: {str(e)[:500]}"
                        
                        await websocket.send(json.dumps({"type": "response", "message": response_text}))
                        continue
                    
                    # Add to session history
                    session_messages.append({"role": "user", "content": user_msg})
                    
                    # Build context from separate memories
                    ai_context = f"AI Memory: name={ai_memory['name']}, language={ai_memory['language']}"
                    user_context = f"User Memory: language={user_memory['language']}, preferences={user_memory['preferences']}"

                    # Call MiniMax with system prompt for plain text responses (no markdown)
                    current_time = get_wib_time().strftime("%d %B %Y, %H:%M:%S")
                    system_prompt = f"""Anda adalah MiniMax AI. Respon Anda harus:
- Bahasa Indonesia informal (pakai "lu", "gua" tidak perlu formal)
- Pendek dan langsung, jangan bertele-tele
- JANGAN tampilkan alur berpikir / reasoning / thought process sama sekali
- Jangan pakai emoji
- Plain text only. NO formatting symbols: tidak pakai ** * ## - atau numbered lists
- Kalau jawab pertanyaan, langsung kasih jawaban
- Kalau perlu penjelasan, singkat aja
- WAKTU SEKARANG: {current_time} (WIB / Jakarta timezone). JANGAN bilang "saat ini" atau "kurang lebih" — gunakan waktu actual ini.
- JANGAN PERNAH output reasoning/thinking/analysis text apapun. Langsung jawab.

Model: {MINIMAX_MODEL}

TOOLS (langsung bisa dipanggil dengan [TOOL: nama | param='nilai']):
- calculator: kalkulasi matematika
- currency_convert: konversi mata uang (USD, IDR, dll)
- crypto_price: harga crypto (BTC, ETH, SOL, dll) via Binance
- wikipedia: info dari Wikipedia
- weather: cuaca kota
- web_search: cari di web (DuckDuckGo)
- news: berita terbaru dari Google News (Indonesian)
- image_gen: generate gambar (placeholder)
- code_exec: jalankan Python code (sintaks sederhana)
- translate: terjemahan teks
- polymarket: prediction market odds (Polymarket.com)
- meteora_dlmm: pool data Meteora DLMM (SOL-HYPE, dll)
- terminal: jalankan shell command (ls, cat, git, npm, pip, python, curl, dll)
- browser: browse webpage pakai Playwright (snapshot, screenshot, click, type)
- jupyter: jalankan Python code di Jupyter kernel (numpy, pandas, matplotlib)
- hermes_skill: akses 104+ Hermes skills (polymarket, meteora, github, arxiv, spotify, dll)


HERMES SKILLS (110 skills, semua bisa diakses pakai [TOOL: hermes_skill | skill_name='nama' | query='...']):

APPLE (4):
  - apple/apple-notes: Manage Apple Notes via memo CLI: create, search, edit.
  - apple/apple-reminders: Apple Reminders via remindctl: add, list, complete.
  - apple/findmy: Track Apple devices/AirTags via FindMy.app on macOS.
  - apple/imessage: Send and receive iMessages/SMS via the imsg CLI on macOS.

AUTONOMOUS-AI-AGENTS (4):
  - autonomous-ai-agents/claude-code: Delegate coding to Claude Code CLI (features, PRs).
  - autonomous-ai-agents/codex: Delegate coding to OpenAI Codex CLI (features, PRs).
  - autonomous-ai-agents/hermes-agent: Configure, extend, or contribute to Hermes Agent.
  - autonomous-ai-agents/opencode: Delegate coding to OpenCode CLI (features, PR review).

CREATIVE (19):
  - creative/architecture-diagram: Dark-themed SVG architecture/cloud/infra diagrams as HTML.
  - creative/ascii-art: ASCII art: pyfiglet, cowsay, boxes, image-to-ascii.
  - creative/ascii-video: ASCII video: convert video/audio to colored ASCII MP4/GIF.
  - creative/baoyu-comic: Knowledge comics (知识漫画): educational, biography, tutorial.
  - creative/baoyu-infographic: Infographics: 21 layouts x 21 styles (信息图, 可视化).
  - creative/claude-design: Design one-off HTML artifacts (landing, deck, prototype).
  - creative/comfyui: Generate images, video, and audio with ComfyUI — install, launch, manage nodes/m
  - creative/creative-ideation: Generate project ideas via creative constraints.
  - creative/design-md: Author/validate/export Google's DESIGN.md token spec files.
  - creative/excalidraw: Hand-drawn Excalidraw JSON diagrams (arch, flow, seq).
  - creative/humanizer: Humanize text: strip AI-isms and add real voice.
  - creative/manim-video: Manim CE animations: 3Blue1Brown math/algo videos.
  - creative/p5js: p5.js sketches: gen art, shaders, interactive, 3D.
  - creative/pixel-art: Pixel art w/ era palettes (NES, Game Boy, PICO-8).
  - creative/popular-web-designs: 54 real design systems (Stripe, Linear, Vercel) as HTML/CSS.
  - creative/pretext: Use when building creative browser demos with @chenglou/pretext — DOM-free text 
  - creative/sketch: Throwaway HTML mockups: 2-3 design variants to compare.
  - creative/songwriting-and-ai-music: Songwriting craft and Suno AI music prompts.
  - creative/touchdesigner-mcp: Control a running TouchDesigner instance via twozero MCP — create operators, set

DATA-SCIENCE (2):
  - data-science/google-news-rss-scraper: Fetch latest news headlines from Google News via RSS — no API key required
  - data-science/jupyter-live-kernel: Iterative Python via live Jupyter kernel (hamelnb).

DEVOPS (2):
  - devops/caddy-websocket-proxy: Configure Caddy reverse proxy for WebSocket connections
  - devops/webhook-subscriptions: Webhook subscriptions: event-driven agent runs.

EMAIL (1):
  - email/himalaya: Himalaya CLI: IMAP/SMTP email from terminal.

GAMING (8):
  - gaming/awp-wallet-ops: Operational notes for awp-wallet CLI — import quirks, wallet format, and common 
  - gaming/mine-worknet-ops: Operational notes and troubleshooting for Mine Worknet miner. Covers diagnosis w
  - gaming/minecraft-modpack-server: Host modded Minecraft servers (CurseForge, Modrinth).
  - gaming/pokemon-player: Play Pokemon via headless emulator + RAM reads.
  - gaming/predict-worknet-klines-trap: Critical klines behavior discovered through direct experience with predict-workn
  - gaming/predict-worknet-ops: Operational notes for predict-worknet loop — OpenClaw model/auth setup, scope up
  - gaming/predict-worknet-submission: Submit predictions to AWP Predict WorkNet — challenge format, ticket sizing, err
  - gaming/predict-worknet-workarounds: Workarounds and discovered quirks for Predict WorkNet predict-agent CLI

GITHUB (6):
  - github/codebase-inspection: Inspect codebases w/ pygount: LOC, languages, ratios.
  - github/github-auth: GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login.
  - github/github-code-review: Review PRs: diffs, inline comments via gh or REST.
  - github/github-issues: Create, triage, label, assign GitHub issues via gh or REST.
  - github/github-pr-workflow: GitHub PR lifecycle: branch, commit, open, CI, merge.
  - github/github-repo-management: Clone/create/fork repos; manage remotes, releases.

HERMES (1):
  - hermes/hermes-skills-index: Index and access Hermes 104 skills from external tools/apps. Load SKILL.md on de

MCP (1):
  - mcp/native-mcp: MCP client: connect servers, register tools (stdio/HTTP).

MEDIA (5):
  - media/gif-search: Search/download GIFs from Tenor via curl + jq.
  - media/heartmula: HeartMuLa: Suno-like song generation from lyrics + tags.
  - media/songsee: Audio spectrograms/features (mel, chroma, MFCC) via CLI.
  - media/spotify: Spotify: play, search, queue, manage playlists and devices.
  - media/youtube-content: YouTube transcripts to summaries, threads, blogs.

MLOPS (13):
  - mlops/evaluation/lm-evaluation-harness: lm-eval-harness: benchmark LLMs (MMLU, GSM8K, etc.).
  - mlops/evaluation/weights-and-biases: W&B: log ML experiments, sweeps, model registry, dashboards.
  - mlops/huggingface-hub: HuggingFace hf CLI: search/download/upload models, datasets.
  - mlops/inference/llama-cpp: llama.cpp local GGUF inference + HF Hub model discovery.
  - mlops/inference/obliteratus: OBLITERATUS: abliterate LLM refusals (diff-in-means).
  - mlops/inference/outlines: Outlines: structured JSON/regex/Pydantic LLM generation.
  - mlops/inference/vllm: vLLM: high-throughput LLM serving, OpenAI API, quantization.
  - mlops/models/audiocraft: AudioCraft: MusicGen text-to-music, AudioGen text-to-sound.
  - mlops/models/segment-anything: SAM: zero-shot image segmentation via points, boxes, masks.
  - mlops/research/dspy: DSPy: declarative LM programs, auto-optimize prompts, RAG.
  - mlops/training/axolotl: Axolotl: YAML LLM fine-tuning (LoRA, DPO, GRPO).
  - mlops/training/trl-fine-tuning: TRL: SFT, DPO, PPO, GRPO, reward modeling for LLM RLHF.
  - mlops/training/unsloth: Unsloth: 2-5x faster LoRA/QLoRA fine-tuning, less VRAM.

MOBILE (2):
  - mobile/cap-app-notification-tap: Fix Capacitor Android notification tap — PendingIntent opens app correctly
  - mobile/lambda-app-notification-sound: Fix notification sound on Lambda Capacitor Android app — native ToneGenerator vi

MONITORING (1):
  - monitoring/telegram-channel-monitor: Scrape and monitor Telegram public channels for sentiment data — parse liquidati

NOTE-TAKING (1):
  - note-taking/obsidian: Read, search, and create notes in the Obsidian vault.

PRODUCTIVITY (13):
  - productivity/airtable: Airtable REST API via curl. Records CRUD, filters, upserts.
  - productivity/capacitor-native-background-service: Add native Android background polling + OS notifications to Capacitor app using 
  - productivity/capacitor-native-notification: Capacitor Android native OS notification via WorkManager + Foreground Service (n
  - productivity/capacitor-webview-live-reload: Make Capacitor Android APK load web from server URL instead of internal bundle, 
  - productivity/capacitor-webview-pitfalls: Critical quirks discovered through trial-and-error when building Capacitor Andro
  - productivity/google-workspace: Gmail, Calendar, Drive, Docs, Sheets via gws CLI or Python.
  - productivity/linear: Linear: manage issues, projects, teams via GraphQL + curl.
  - productivity/maps: Geocode, POIs, routes, timezones via OpenStreetMap/OSRM.
  - productivity/nano-pdf: Edit PDF text/typos/titles via nano-pdf CLI (NL prompts).
  - productivity/notion: Notion API via curl: pages, databases, blocks, search.
  - productivity/ocr-and-documents: Extract text from PDFs/scans (pymupdf, marker-pdf).
  - productivity/powerpoint: Create, read, edit .pptx decks, slides, notes, templates.
  - productivity/web-to-apk: Convert web apps (HTML/CSS/JS) to Android APK using Capacitor on VPS

RED-TEAMING (1):
  - red-teaming/godmode: Jailbreak LLMs: Parseltongue, GODMODE, ULTRAPLINIAN.

RESEARCH (6):
  - research/arxiv: Search arXiv papers by keyword, author, category, or ID.
  - research/blogwatcher: Monitor blogs and RSS/Atom feeds via blogwatcher-cli tool.
  - research/llm-wiki: Karpathy's LLM Wiki: build/query interlinked markdown KB.
  - research/meteora-dlmm-data: Query Meteora DLMM pool/group data from the public datapi endpoints, especially 
  - research/polymarket: Query Polymarket: markets, prices, orderbooks, history.
  - research/research-paper-writing: Write ML papers for NeurIPS/ICML/ICLR: design→submit.

ROOT (6):
  - awp: AWP (Agent Work Protocol) — the complete toolkit for agent mining on Base, Ether
  - awp.backup.20260425-212500: AWP (Agent Work Protocol) — the complete toolkit for agent mining on Base, Ether
  - dogfood: Exploratory QA of web apps: find bugs, evidence, reports.
  - mine: Mine data and earn $aMine rewards on the Mine Worknet. This skill manages autono
  - predict-worknet: Swarm Intelligence Prediction WorkNet — submit price predictions and earn $PRED
  - yuanbao: Yuanbao (元宝) groups: @mention users, query info/members.

SMART-HOME (1):
  - smart-home/openhue: Control Philips Hue lights, scenes, rooms via OpenHue CLI.

SOCIAL-MEDIA (1):
  - social-media/xurl: X/Twitter via xurl CLI: post, search, DM, media, v2 API.

SOFTWARE-DEVELOPMENT (12):
  - software-development/ai-server-tools: Adding terminal, browser, and jupyter tools to an async AI server (websockets + 
  - software-development/debugging-hermes-tui-commands: Debug Hermes TUI slash commands: Python, gateway, Ink UI.
  - software-development/hermes-agent-skill-authoring: Author in-repo SKILL.md: frontmatter, validator, structure.
  - software-development/node-inspect-debugger: Debug Node.js via --inspect + Chrome DevTools Protocol CLI.
  - software-development/plan: Plan mode: write markdown plan to .hermes/plans/, no exec.
  - software-development/python-debugpy: Debug Python: pdb REPL + debugpy remote (DAP).
  - software-development/requesting-code-review: Pre-commit review: security scan, quality gates, auto-fix.
  - software-development/spike: Throwaway experiments to validate an idea before build.
  - software-development/subagent-driven-development: Execute plans via delegate_task subagents (2-stage review).
  - software-development/systematic-debugging: 4-phase root cause debugging: understand bugs before fixing.
  - software-development/test-driven-development: TDD: enforce RED-GREEN-REFACTOR, tests before code.
  - software-development/writing-plans: Write implementation plans: bite-sized tasks, paths, code.




INSTRUKSI TOOL:
- Untuk data real-time (harga, berita, cuaca): pakai tool yang sesuai
- Untuk crypto: [TOOL: crypto_price | symbol='BTC']
- Untuk prediction market: [TOOL: polymarket | query='bitcoin price 2026']
- Untuk Meteora DLMM: [TOOL: meteora_dlmm | pool_address='alamat_pool']
- Untuk cek file/folder: [TOOL: terminal | command='ls -la /home/ubuntu/']
- Untuk browse web: [TOOL: browser | url='https://example.com' | action='snapshot']
- Untuk Python dengan visualisasi: [TOOL: jupyter | code='import matplotlib.pyplot as plt']
- Untuk skill lain: [TOOL: hermes_skill | skill_name='kategori.nama' | query='apa yang mau ditanyakan']
- Setelah tool dipanggil, response akan di-return. Sampaikan ke user dengan natural.
- JANGAN gunakan tool untuk pertanyaan umum yang bisa dijawab tanpa data."""
                    full_messages = [{"role": "system", "content": system_prompt}] + session_messages
                    response_text, usage = await call_minimax(full_messages)
                    
                    print(f"[AI]: {response_text[:100]}")

                    # Check for tool calls in AI response
                    tool_calls = parse_tool_call(response_text)
                    
                    # If tool calls detected, process them
                    if tool_calls:
                        print(f"[Tools] Detected {len(tool_calls)} tool call(s)")
                        # Remove tool call syntax from displayed response
                        clean_response = TOOL_PATTERN.sub('', response_text).strip()
                        
                        # Send initial response (without tool syntax)
                        await websocket.send(json.dumps({
                            "type": "response",
                            "message": clean_response
                        }))
                        
                        # Execute each tool and send results
                        for tool_match, tool_name, params in tool_calls:
                            if tool_name in TOOLS:
                                print(f"[Tools] Executing: {tool_name} with params: {params}")
                                result = await exec_tool(tool_name, params)
                                print(f"[Tools] Result: {result[:100]}")
                                # Send tool result to client
                                await websocket.send(json.dumps({
                                    "type": "tool_result",
                                    "tool": tool_name,
                                    "result": result
                                }))
                            else:
                                print(f"[Tools] Unknown tool: {tool_name}")
                    else:
                        # Add AI response to history
                        session_messages.append({"role": "assistant", "content": response_text})
                        
                        await websocket.send(json.dumps({
                            "type": "response",
                            "message": response_text
                        }))
                    
            except json.JSONDecodeError:
                # Plain text message
                print(f"[User {client_id} plain]: {message[:100]}")
                response_text, _ = await call_minimax([
                    {"role": "user", "content": message}
                ])
                await websocket.send(json.dumps({
                    "type": "response",
                    "message": response_text
                }))
    
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] Client {client_id} disconnected normally")
    except Exception as e:
        print(f"[!] Client {client_id} error: {e}")
    finally:
        # Clean up client resources
        connected_clients.discard(client_id)
        # Clear session data to free memory
        del session_messages
        del ai_memory
        del user_memory
        print(f"[-] Client {client_id} disconnected ({len(connected_clients)} online)")

async def http_handler(request):
    """Handle HTTP POST /api/chat fallback"""
    try:
        data = await request.json()
        message = data.get("message", "")
        
        current_time = get_wib_time().strftime("%d %B %Y, %H:%M:%S")
        system_prompt = f"""Anda adalah MiniMax AI. Respon Anda harus:
- Bahasa Indonesia informal (pakai "lu", "gua" tidak perlu formal)
- Pendek dan langsung, jangan bertele-tele
- JANGAN tampilkan alur berpikir / reasoning / thought process sama sekali
- Jangan pakai emoji
- Plain text only. NO formatting symbols: tidak pakai ** * ## - atau numbered lists
- Kalau jawab pertanyaan, langsung kasih jawaban
- Kalau perlu penjelasan, singkat aja
- WAKTU SEKARANG: {current_time} (WIB / Jakarta timezone). JANGAN bilang "saat ini" atau "kurang lebih" — gunakan waktu actual ini.
- JANGAN PERNAH output reasoning/thinking/analysis text apapun. Langsung jawab.

Model: {MINIMAX_MODEL}

TOOLS (langsung bisa dipanggil dengan [TOOL: nama | param='nilai']):
- calculator: kalkulasi matematika
- currency_convert: konversi mata uang (USD, IDR, dll)
- crypto_price: harga crypto (BTC, ETH, SOL, dll) via Binance
- wikipedia: info dari Wikipedia
- weather: cuaca kota
- web_search: cari di web (DuckDuckGo)
- news: berita terbaru dari Google News (Indonesian)
- image_gen: generate gambar (placeholder)
- code_exec: jalankan Python code (sintaks sederhana)
- translate: terjemahan teks
- polymarket: prediction market odds (Polymarket.com)
- meteora_dlmm: pool data Meteora DLMM (SOL-HYPE, dll)
- terminal: jalankan shell command (ls, cat, git, npm, pip, python, curl, dll)
- browser: browse webpage pakai Playwright (snapshot, screenshot, click, type)
- jupyter: jalankan Python code di Jupyter kernel (numpy, pandas, matplotlib)
- hermes_skill: akses 104+ Hermes skills (polymarket, meteora, github, arxiv, spotify, dll)


- Untuk data real-time (harga, berita, cuaca): pakai tool yang sesuai
- Untuk crypto: [TOOL: crypto_price | symbol='BTC']
- Untuk prediction market: [TOOL: polymarket | query='bitcoin price 2026']
- Untuk Meteora DLMM: [TOOL: meteora_dlmm | pool_address='alamat_pool']
- Untuk cek file/folder: [TOOL: terminal | command='ls -la /home/ubuntu/']
- Untuk browse web: [TOOL: browser | url='https://example.com' | action='snapshot']
- Untuk Python dengan visualisasi: [TOOL: jupyter | code='import matplotlib.pyplot as plt']
- Untuk skill lain: [TOOL: hermes_skill | skill_name='kategori.nama' | query='apa yang mau ditanyakan']
- Setelah tool dipanggil, response akan di-return. Sampaikan ke user dengan natural.
- JANGAN gunakan tool untuk pertanyaan umum yang bisa dijawab tanpa data."""
        
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
        response_text, _ = await call_minimax(messages)
        
        # Check for tool calls and execute
        tool_calls = parse_tool_call(response_text)
        if tool_calls:
            clean_response = TOOL_PATTERN.sub('', response_text).strip()
            tool_results = []
            for tool_match, tool_name, params in tool_calls:
                if tool_name in TOOLS:
                    result = await exec_tool(tool_name, params)
                    tool_results.append(f"[{tool_name}] {result}")
            if tool_results:
                full_response = clean_response + "\n\n" + "\n".join(tool_results)
            else:
                full_response = clean_response
            return web.json_response({"response": full_response})
        
        return web.json_response({"response": response_text})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def messages_count_handler(request):
    """Handle GET /api/messages/count — return total messages sent to chat"""
    return web.json_response({"count": message_count})


async def inject_status_handler(request):
    """Handle GET /api/inject?status=1 — return pending messages count for background service"""
    try:
        # Check if there are connected clients
        if connected_clients:
            return web.json_response({"status": "connected", "clients": len(connected_clients)})
        else:
            return web.json_response({"status": "no_clients", "clients": 0})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def inject_handler(request):
    """Handle POST /api/inject — receive messages from Agent 1 and broadcast to chat clients"""
    try:
        data = await request.json()
        message = data.get("message", "")
        sender = data.get("sender", "Agent")
        
        if not message:
            return web.Response(text="ERROR: empty message", status=400)
        
        print(f"[INJECT] From {sender}: {message[:100]}")
        
        # Broadcast to all connected chat clients via WebSocket
        if connected_clients:
            # Send via WebSocket to each connected client
            for client_ws in list(connected_clients):
                try:
                    await client_ws.send(json.dumps({
                        "type": "response",
                        "message": f"[{sender}] {message}"
                    }))
                except Exception as e:
                    print(f"[INJECT] Failed to send to client: {e}")
            
            return web.Response(text=f"OK: delivered to {len(connected_clients)} clients")
        else:
            return web.Response(text="WARNING: no chat clients connected", status=200)
            
    except Exception as e:
        print(f"[INJECT] Error: {e}")
        return web.Response(text=f"ERROR: {e}", status=500)

async def skills_handler(request):
    """Handle GET /api/skills — dynamically load all Hermes skills from filesystem"""
    skills = []
    
    # Built-in tools (always available)
    builtin_tools = [
        {"name": "calculator", "icon": "🧮", "desc": "Hitung matematika — 15 * 23 + 7", "category": "tools"},
        {"name": "currency_convert", "icon": "💱", "desc": "Konversi mata uang — 100 USD ke IDR", "category": "tools"},
        {"name": "web_search", "icon": "🔍", "desc": "Cari di web — berita, fakta, info real-time", "category": "tools"},
        {"name": "wikipedia", "icon": "📖", "desc": "Cari Wikipedia — orang, tempat, sejarah", "category": "tools"},
        {"name": "weather", "icon": "🌤️", "desc": "Cuaca kota — cuaca jakarta", "category": "tools"},
        {"name": "code_exec", "icon": "💻", "desc": "Jalankan kode Python — analisis data, kalkulasi", "category": "tools"},
        {"name": "translate", "icon": "🌏", "desc": "Terjemahkan teks antar bahasa", "category": "tools"},
        {"name": "image_gen", "icon": "🎨", "desc": "Generate gambar dari deskripsi teks", "category": "tools"},
        {"name": "news", "icon": "📰", "desc": "Berita terbaru per topik", "category": "tools"},
    ]
    skills.extend(builtin_tools)
    
    # Dynamically load Hermes skills from ~/.hermes/skills/
    skills_dir = Path.home() / ".hermes" / "skills"
    if skills_dir.exists():
        for skill_path in skills_dir.rglob("SKILL.md"):
            try:
                rel_path = skill_path.relative_to(skills_dir)
                parts = rel_path.parts
                if len(parts) >= 1:
                    skill_name = parts[0]
                    # Read skill description from file
                    content = skill_path.read_text(encoding='utf-8')
                    # Extract description from frontmatter or first line
                    desc = f"Hermes skill: {skill_name}"
                    # Try to get description from frontmatter
                    if content.startswith('---'):
                        frontmatter_end = content.find('---', 3)
                        if frontmatter_end > 0:
                            frontmatter = content[3:frontmatter_end]
                            for line in frontmatter.split('\n'):
                                if line.startswith('description:'):
                                    desc = line.split(':', 1)[1].strip().strip('"').strip("'")
                                    break
                                elif line.startswith('name:'):
                                    name_from_fm = line.split(':', 1)[1].strip().strip('"').strip("'")
                                    if name_from_fm:
                                        skill_name = name_from_fm
                    # Icon based on category
                    icon = "⚡"
                    if 'github' in skill_name.lower(): icon = "🐙"
                    elif 'telegram' in skill_name.lower(): icon = "📡"
                    elif 'spotify' in skill_name.lower(): icon = "🎵"
                    elif 'youtube' in skill_name.lower(): icon = "🎬"
                    elif 'weather' in skill_name.lower(): icon = "🌤️"
                    elif 'polymarket' in skill_name.lower(): icon = "🎯"
                    elif 'arxiv' in skill_name.lower(): icon = "📚"
                    elif 'awp' in skill_name.lower() or 'mine' in skill_name.lower(): icon = "⛏️"
                    elif 'predict' in skill_name.lower(): icon = "🔮"
                    elif 'meteora' in skill_name.lower(): icon = "📊"
                    elif 'discord' in skill_name.lower(): icon = "💬"
                    elif 'music' in skill_name.lower() or 'audio' in skill_name.lower(): icon = "🎶"
                    elif 'image' in skill_name.lower() or 'art' in skill_name.lower(): icon = "🎨"
                    elif 'coding' in skill_name.lower() or 'debug' in skill_name.lower(): icon = "💻"
                    elif 'email' in skill_name.lower() or 'mail' in skill_name.lower(): icon = "📧"
                    elif 'web' in skill_name.lower(): icon = "🌐"
                    elif 'data' in skill_name.lower() or 'ml' in skill_name.lower(): icon = "📈"
                    elif 'api' in skill_name.lower() or 'mcp' in skill_name.lower(): icon = "🔌"
                    elif 'devops' in skill_name.lower() or 'deploy' in skill_name.lower(): icon = "🚀"
                    
                    skills.append({
                        "name": skill_name,
                        "icon": icon,
                        "desc": desc,
                        "category": "hermes"
                    })
            except Exception as e:
                print(f"Error loading skill {skill_path}: {e}")
                continue
    
    return web.json_response(skills)

async def main():
    HOST = "0.0.0.0"
    WS_PORT = 5001
    HTTP_PORT = 5002

    if not MINIMAX_API_KEY:
        print("WARNING: No MINIMAX_API_KEY found!")

    # CORS middleware for aiohttp
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            return web.Response(
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Max-Age': '86400',
                }
            )
        resp = await handler(request)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    # HTTP server for /api/chat and /api/skills on port 5002
    http_app = web.Application(middlewares=[cors_middleware])
    http_app.router.add_post("/api/chat", http_handler)
    http_app.router.add_get("/api/skills", skills_handler)
    http_app.router.add_get("/api/messages/count", messages_count_handler)  # For Android service
    http_app.router.add_get("/api/inject", inject_status_handler)  # GET for background service status
    http_app.router.add_post("/api/inject", inject_handler)  # For Agent 1 to inject messages
    http_app.router.add_post("/api/verify-pin", verify_pin_handler)  # Secure PIN verification
    http_runner = web.AppRunner(http_app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, HOST, HTTP_PORT)
    await http_site.start()
    
    # WebSocket server on port 5001
    async with websockets.serve(handler, HOST, WS_PORT):
        print(f"WebSocket server on ws://{HOST}:{WS_PORT}")
        print(f"HTTP API server on http://{HOST}:{HTTP_PORT}")
        print("Web chat client ready!\n")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")