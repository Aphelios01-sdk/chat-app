#!/usr/bin/env python3
"""
MCP Bridge Server - Agent-to-ChatApp Bridge
Listens for Agent 1 messages and broadcasts to ChatApp WebSocket clients
All on ONE port (5004) for Cloudflared tunnel compatibility.
"""

import asyncio
import json
from aiohttp import web
from aiohttp.web import WSMsgType
from datetime import datetime

chat_clients = set()
bridge_running = True


async def websocket_handler(request):
    """Handle incoming WebSocket connections from chat app"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    chat_clients.add(ws)
    client_id = id(ws)
    print(f"[WS] Chat client {client_id} connected ({len(chat_clients)} online)")

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                pass  # Chat app rarely sends, but keep alive
            elif msg.type == WSMsgType.ERROR:
                break
    except Exception as e:
        print(f"[WS] Client {client_id} error: {e}")
    finally:
        chat_clients.discard(ws)
        print(f"[WS] Chat client {client_id} disconnected ({len(chat_clients)} online)")

    return ws


async def inject_handler(request):
    """HTTP endpoint for Agent 1 to inject messages"""
    try:
        data = await request.json()
        message = data.get("message", "")
        sender = data.get("sender", "Agent")

        if not message:
            return web.Response(text="ERROR: empty message", status=400)

        print(f"[INJECT] From {sender}: {message[:100]}")

        if chat_clients:
            broadcast_data = {
                "type": "response",
                "message": message,
                "sender": sender
            }

            disconnected = set()
            for client in chat_clients:
                try:
                    await client.send_json(broadcast_data)
                except Exception:
                    disconnected.add(client)

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


async def main():
    """Start unified HTTP+WebSocket server on port 5004"""
    global bridge_running

    app = web.Application()
    app.router.add_get('/ws', websocket_handler)
    app.router.add_post('/inject', inject_handler)
    app.router.add_get('/status', status_handler)
    app.router.add_get('/clients', lambda r: web.json_response({"client_count": len(chat_clients)}))

    port = 5004
    http_runner = web.AppRunner(app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, '0.0.0.0', port)
    await http_site.start()
    print(f"[READY] MCP Bridge running on http://0.0.0.0:{port}")
    print(f"[READY] WS endpoint: ws://0.0.0.0:{port}/ws")
    print(f"[READY] HTTP endpoint: http://0.0.0.0:{port}/inject")

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
