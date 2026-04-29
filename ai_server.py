#!/usr/bin/env python3
"""
AI Chat Server - MiniMax Real AI Version
Web chat connects here -> calls MiniMax API
Same AI as Telegram!
"""

import os
import json
import asyncio
import websockets
import requests
from datetime import datetime
from pathlib import Path

connected_clients = set()

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
                
                if data.get("type") == "chat":
                    user_msg = data.get("message", "")
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
                    
                    # Add to session history
                    session_messages.append({"role": "user", "content": user_msg})
                    
                    # Build context from separate memories
                    ai_context = f"AI Memory: name={ai_memory['name']}, language={ai_memory['language']}"
                    user_context = f"User Memory: language={user_memory['language']}, preferences={user_memory['preferences']}"
                    
                    # Call MiniMax with system prompt for plain text responses (no markdown)
                    system_prompt = f"You are {ai_memory['name']}. You have separate memory from the user. AI Memory: {ai_context}. User Memory: {user_context}. When a user mentions or asks about 'skill', 'skills', or a specific skill name (like 'awp', 'predict', 'github', 'jupyter', etc.), understand that these refer to special capabilities or workflows you can help with. If asked about a skill, briefly explain what it does and offer to help use it. Always respond in plain text only. Do NOT use any markdown formatting such as **bold**, ## headers, *italics*, - bullet points, numbered lists, or any other markdown syntax. Write as simple plain paragraphs. Do NOT use emoji."
                    full_messages = [{"role": "system", "content": system_prompt}] + session_messages
                    response_text, usage = await call_minimax(full_messages)
                    
                    print(f"[AI]: {response_text[:100]}")
                    
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

async def main():
    HOST = "0.0.0.0"
    PORT = 5001
    
    if not MINIMAX_API_KEY:
        print("WARNING: No MINIMAX_API_KEY found!")
    
    async with websockets.serve(handler, HOST, PORT):
        print(f"Server running on ws://{HOST}:{PORT}")
        print("Web chat client ready!\n")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")