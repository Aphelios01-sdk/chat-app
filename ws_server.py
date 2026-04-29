#!/usr/bin/env python3
"""
Chat Server - WebSocket Version
Compatible with web app (index.html)
"""

import asyncio
import websockets
import json
from datetime import datetime

connected_clients = {}
USERS = {}

async def handler(websocket, path):
    """Handle client connection"""
    try:
        # Wait for nickname
        nickname = await websocket.recv()
        nickname = nickname.strip() or f"User{len(connected_clients) + 1}"
        
        connected_clients[websocket] = nickname
        USERS[nickname] = websocket
        
        print(f"[+] {nickname} connected ({len(connected_clients)} online)")
        await broadcast(f"[{nickname}] bergabung!", exclude=websocket)
        await send_user_list()
        
        async for message in websocket:
            if not message:
                break
            
            msg = message.strip()
            
            if msg.startswith("/nick "):
                new_nick = msg[6:].strip()
                if new_nick and new_nick not in USERS:
                    old_nick = connected_clients[websocket]
                    del USERS[old_nick]
                    connected_clients[websocket] = new_nick
                    USERS[new_nick] = websocket
                    await broadcast(f"{old_nick} → {new_nick}")
                    await websocket.send(f"Nickname diubah ke {new_nick}")
                elif new_nick in USERS:
                    await websocket.send("Nickname sudah digunakan!")
                else:
                    await websocket.send("Nickname tidak valid!")
            
            elif msg.startswith("/msg "):
                parts = msg[4:].split(" ", 1)
                if len(parts) == 2:
                    target, text = parts
                    if target in USERS:
                        pm_msg = f"[PM dari {connected_clients[websocket]}] {text}"
                        await USERS[target].send(pm_msg)
                        await websocket.send(pm_msg)
                    else:
                        await websocket.send(f"User '{target}' tidak ditemukan")
                else:
                    await websocket.send("Format: /msg [user] [text]")
            
            elif msg == "/list":
                online = list(USERS.keys())
                await websocket.send(json.dumps({
                    "type": "list",
                    "users": online
                }))
            
            elif msg == "/help":
                help_text = """
Perintah:
/nick [nama] - Ganti nickname
/msg [user] [text] - Kirim PM
/list - User online
/help - Bantuan
"""
                await websocket.send(help_text)
            
            elif msg == "/clear":
                await websocket.send("CLEAR")
            
            else:
                # Broadcast ke semua
                sender = connected_clients[websocket]
                await broadcast(f"[{sender}] {msg}", exclude=websocket)
                print(f"[{sender}] {msg}")
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in connected_clients:
            nickname = connected_clients.pop(websocket)
            if nickname in USERS:
                del USERS[nickname]
            print(f"[-] {nickname} disconnected ({len(connected_clients)} online)")
            await broadcast(f"[{nickname}] telah keluar")

async def broadcast(message, exclude=None):
    """Kirim pesan ke semua client"""
    for client, nickname in connected_clients.items():
        if client != exclude:
            try:
                await client.send(message)
            except:
                pass

async def send_user_list():
    """Kirim daftar user ke semua client"""
    online = list(USERS.keys())
    msg = json.dumps({"type": "list", "users": online})
    for client in connected_clients:
        try:
            await client.send(msg)
        except:
            pass

async def main():
    HOST = '0.0.0.0'
    PORT = 5000
    
    print("╔══════════════════════════════════════╗")
    print("║     WEBSOCKET CHAT SERVER v1.0        ║")
    print("╚══════════════════════════════════════╝")
    print(f"Server running on ws://{HOST}:{PORT}")
    print("Menunggu koneksi...\n")
    
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer dimatikan...")
