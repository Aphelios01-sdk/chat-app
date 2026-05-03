#!/usr/bin/env python3
"""
Lambda Bridge Server
Web chat frontend connects here -> forwards to AI API
Same model as Telegram chat!
"""

import os
import re
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional

# Try to import flask, fall back to aiohttp
try:
    from flask import Flask, request, jsonify, Response
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask not available, using aiohttp only")

# Configuration - get from environment
LAMBDA_API_KEY = os.environ.get("LAMBDA_API_KEY", "")
LAMBDA_API_URL = os.environ.get("LAMBDA_API_URL", "https://api.ai.io")
LAMBDA_MODEL = os.environ.get("LAMBDA_MODEL", "Lambda-AI")
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", "5002"))

# If no API key in env, try to get from hermes config
if not LAMBDA_API_KEY:
    from pathlib import Path
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("LAMBDA_API_KEY="):
                LAMBDA_API_KEY = line.split("=", 1)[1].strip().strip('"')
                break

print(f"╔══════════════════════════════════════════════╗")
print(f"║     Lambda Bridge Server                ║")
print(f"╚══════════════════════════════════════════════╝")
print(f"Model: {LAMBDA_MODEL}")
print(f"API Key: {'*' * 20}{LAMBDA_API_KEY[-10:] if LAMBDA_API_KEY else 'NOT FOUND'}")
print(f"Port: {BRIDGE_PORT}")

# Flask app
if FLASK_AVAILABLE:
    app = Flask(__name__)

    @app.route("/v1/models", methods=["GET"])
    def list_models():
        """OpenAI-compatible models endpoint"""
        return jsonify({
            "object": "list",
            "data": [{
                "id": LAMBDA_MODEL,
                "object": "model",
                "created": 1699999999,
                "owned_by": "ai",
                "permission": [],
                "root": LAMBDA_MODEL,
                "parent": None
            }]
        })

    @app.route("/v1/chat/completions", methods=["POST"])
    def chat_completions():
        """OpenAI-compatible chat completions endpoint"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400

            messages = data.get("messages", [])
            model = data.get("model", LAMBDA_MODEL)
            max_tokens = data.get("max_tokens", 4096)
            temperature = data.get("temperature", 0.7)
            stream = data.get("stream", False)

            # Build AI API request
            headers = {
                "Authorization": f"Bearer {LAMBDA_API_KEY}",
                "Content-Type": "application/json",
                "x-api-provider": "lambda"
            }

            # Convert messages format for AI
            ai_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Map roles
                if role == "system":
                    role = "user"  # AI doesn't have system role in same way
                    content = f"[System] {content}"
                elif role == "assistant":
                    role = "assistant"
                elif role == "tool":
                    role = "user"
                    content = f"[Tool Result] {content}"
                
                ai_messages.append({
                    "role": role,
                    "content": content
                })

            payload = {
                "model": model,
                "messages": ai_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }

            # For streaming, we need SSE response
            if stream:
                def generate():
                    # Sync call - for real streaming need aiohttp
                    yield "data: {\"error\": \"Streaming not implemented yet\"}\n\n"
                
                return Response(generate(), mimetype="text/event-stream")

            # Make synchronous request to AI
            import requests
            api_path = "/v1/chat/completions" if "AI" in model else "/v1/chat/completions"
            
            if "AI" in model:
                # Use Anthropic-compatible endpoint
                url = f"{LAMBDA_API_URL}/v1/chat/completions"
                response = requests.post(url, headers=headers, json=payload, timeout=60)
            else:
                url = f"{LAMBDA_API_URL}/v1/chat/completions"
                response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code != 200:
                return jsonify({
                    "error": {
                        "message": response.text,
                        "type": "api_error",
                        "code": response.status_code
                    }
                }), response.status_code

            result = response.json()
            
            # Convert back to OpenAI format
            if "content" in result:
                # Anthropic format
                content = result["content"]
                if isinstance(content, list):
                    text = "".join([c.get("text", "") for c in content if c.get("type") == "text"])
                else:
                    text = content
                
                return jsonify({
                    "id": f"chatcmpl-{result.get('id', 'unknown')}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": text
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": result.get("usage", {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    })
                })
            else:
                # OpenAI format
                return jsonify(result)

        except Exception as e:
            import traceback
            return jsonify({
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": "INTERNAL_ERROR"
                }
            }), 500

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "model": LAMBDA_MODEL})

    if __name__ == "__main__":
        if not LAMBDA_API_KEY:
            print("WARNING: No LAMBDA_API_KEY found!")
            print("Set it via environment variable or edit the .env file")
        
        app.run(host="0.0.0.0", port=BRIDGE_PORT, debug=False, threaded=True)
else:
    # Pure aiohttp version
    print("Using aiohttp server")
    
    async def handle_chat_completions(data, session):
        """Handle chat completions request"""
        messages = data.get("messages", [])
        model = data.get("model", LAMBDA_MODEL)
        max_tokens = data.get("max_tokens", 4096)
        temperature = data.get("temperature", 0.7)
        
        # Build AI API request
        headers = {
            "Authorization": f"Bearer {LAMBDA_API_KEY}",
            "Content-Type": "application/json",
            "x-api-provider": "lambda"
        }
        
        # Convert messages
        ai_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                role = "user"
                content = f"[System] {content}"
            elif role == "assistant":
                role = "assistant"
            elif role == "tool":
                role = "user"
                
            ai_messages.append({"role": role, "content": content})
        
        payload = {
            "model": model,
            "messages": ai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        url = f"{LAMBDA_API_URL}/v1/chat/completions"
        
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            result = await resp.json()
            
            if resp.status != 200:
                return {
                    "error": {
                        "message": str(result),
                        "type": "api_error",
                        "code": resp.status
                    }
                }, resp.status
            
            # Convert to OpenAI format
            content = result.get("content", "")
            if isinstance(content, list):
                text = "".join([c.get("text", "") for c in content if c.get("type") == "text"])
            else:
                text = content
            
            return {
                "id": f"chatcmpl-{result.get('id', 'unknown')}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop"
                }],
                "usage": result.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            }, 200

    async def handler(request):
        """aiohttp handler"""
        if request.path == "/health":
            return aiohttp.web.json_response({"status": "ok", "model": LAMBDA_MODEL})
        
        if request.path == "/v1/chat/completions" and request.method == "POST":
            try:
                data = await request.json()
                result, status = await handle_chat_completions(data, request.app['session'])
                return aiohttp.web.json_response(result, status=status)
            except Exception as e:
                return aiohttp.web.json_response({
                    "error": {"message": str(e), "type": "internal_error"}
                }, status=500)
        
        if request.path == "/v1/models" and request.method == "GET":
            return aiohttp.web.json_response({
                "object": "list",
                "data": [{
                    "id": LAMBDA_MODEL,
                    "object": "model",
                    "created": 1699999999,
                    "owned_by": "ai"
                }]
            })
        
        return aiohttp.web.Response(text="Not Found", status=404)

    async def init_app():
        app = aiohttp.web.Application()
        app['session'] = aiohttp.ClientSession()
        app.router.add_route("*", "/{path:.*}", handler)
        return app

    def run_server():
        if not LAMBDA_API_KEY:
            print("WARNING: No LAMBDA_API_KEY found!")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = loop.run_until_complete(init_app())
        aiohttp.web.run_app(app, host="0.0.0.0", port=BRIDGE_PORT)

    run_server()