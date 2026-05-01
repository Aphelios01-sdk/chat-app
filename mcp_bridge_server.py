#!/usr/bin/env python3
"""
MCP Bridge Server - Agent-to-ChatApp Bridge
Listens for Agent 1 messages and broadcasts to ChatApp WebSocket clients

Usage:
  curl -X POST http://43.156.57.226:5002/inject \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello from Agent 1", "sender": "Agent 1"}'
"""

import asyncio
import json
import websockets
import threading
import sys
from aiohttp import web
from datetime import datetime

# Store connected WebSocket clients (chat app clients)
chat_clients = set()

# Bridge server running flag
bridge_running = True

async def websocket_handler(websocket):
    """Handle incoming WebSocket connections from chat app"""
    chat_clients.add(websocket)
    client_id = id(websocket)
    print(f"[WS] Chat client {client_id} connected ({len(chat_clients)} online)")
    
    try:
        async for message in websocket:
            # Chat app rarely sends, but keep connection alive
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        chat_clients.discard(websocket)
        print(f"[WS] Chat client {client_id} disconnected ({len(chat_clients)} online)")

async def inject_handler(request):
    """HTTP endpoint for Agent 1 to inject messages"""
    try:
        data = await request.json()
        message = data.get("message", "")
        sender = data.get("sender", "Agent")
        
        if not message:
            return web.Response(text="ERROR: empty message", status=400)
        
        print(f"[INJECT] From {sender}: {message[:100]}")
        
        # Broadcast to all connected chat clients
        if chat_clients:
            broadcast_data = {
                "type": "response",
                "message": message,
                "sender": sender
            }
            
            # Send to all connected clients concurrently
            disconnected = set()
            for client in list(chat_clients):
                try:
                    await client.send(json.dumps(broadcast_data))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
            
            # Cleanup disconnected clients
            chat_clients.difference_update(disconnected)
            
            print(f"[INJECT] Broadcast to {len(chat_clients)} clients")
            return web.Response(text=f"OK: delivered to {len(chat_clients)} clients")
        else:
            print(f"[INJECT] No chat clients connected")
            return web.Response(text="WARNING: no chat clients connected", status=200)
            
    except Exception as e:
        print(f"[INJECT] Error: {e}")
        return web.Response(text=f"ERROR: {e}", status=500)

async def status_handler(request):
    """Status check endpoint"""
    return web.json_response({
        "status": "running",
        "chat_clients": len(chat_clients),
        "timestamp": datetime.now().isoformat()
    })

async def list_clients_handler(request):
    """List connected chat clients"""
    return web.json_response({
        "client_count": len(chat_clients),
        "clients": [id(c) for c in chat_clients]
    })

async def broadcast_handler(request):
    """Broadcast a message to all chat clients without HTTP overhead (internal)"""
    try:
        data = await request.json()
        message = data.get("message", "")
        
        if not message:
            return web.Response(text="ERROR: empty message", status=400)
        
        if chat_clients:
            broadcast_data = {
                "type": "response",
                "message": message
            }
            
            disconnected = set()
            for client in list(chat_clients):
                try:
                    await client.send(json.dumps(broadcast_data))
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
            
            chat_clients.difference_update(disconnected)
            return web.Response(text=f"OK: {len(chat_clients)} clients")
        
        return web.Response(text="WARNING: no clients", status=200)
        
    except Exception as e:
        return web.Response(text=f"ERROR: {e}", status=500)

async def ws_to_chat(websocket):
    """WebSocket client that connects to the main chat WebSocket server
    This allows bridging external messages to the chat app via WebSocket protocol"""
    global chat_clients
    
    chat_ws_url = "ws://43.156.57.226/ws"
    
    while bridge_running:
        try:
            async with websockets.connect(chat_ws_url) as ws:
                print(f"[BRIDGE WS] Connected to main chat server")
                
                # Register with main server
                await ws.send(json.dumps({
                    "type": "chat",
                    "message": "/bridge_connected",
                    "history": []
                }))
                
                # Listen for commands from main server
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        if data.get("type") == "response":
                            # Got a response, relay to all chat_clients
                            for client in list(chat_clients):
                                try:
                                    await client.send(json.dumps(data))
                                except:
                                    pass
                    except:
                        pass
                        
        except Exception as e:
            print(f"[BRIDGE WS] Disconnected: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)

async def main():
    """Start both HTTP and WebSocket servers"""
    global bridge_running
    
    # HTTP server for Agent 1 to call
    app = web.Application()
    app.router.add_post('/inject', inject_handler)
    app.router.add_get('/status', status_handler)
    app.router.add_get('/clients', list_clients_handler)
    
    # Start HTTP server
    http_port = 5004
    http_runner = web.AppRunner(app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, '0.0.0.0', http_port)
    await http_site.start()
    print(f"[HTTP] MCP Bridge listening on http://0.0.0.0:{http_port}")
    
    # WebSocket server for chat app connections
    ws_port = 5003
    ws_server = websockets.serve(websocket_handler, '0.0.0.0', ws_port)
    print(f"[WS] Chat bridge server listening on ws://0.0.0.0:{ws_port}")
    
    # Start WebSocket server
    async with ws_server:
        print(f"[READY] MCP Bridge Server running!")
        print(f"[READY] HTTP endpoint: http://43.156.57.226:{http_port}/inject")
        print(f"[READY] WS endpoint: ws://43.156.57.226:{ws_port}")
        
        # Keep running
        while bridge_running:
            await asyncio.sleep(1)

def stop():
    global bridge_running
    bridge_running = False

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOPPED] MCP Bridge Server")
        stop()
