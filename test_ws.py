#!/usr/bin/env python3
import asyncio
import websockets

async def handler(websocket, path):
    print('Client connected!')
    msg = await websocket.recv()
    print(f'Received: {msg}')
    await websocket.send('Hello from server!')
    print('Sent response')

async def main():
    async with websockets.serve(handler, '0.0.0.0', 5008):
        print('Server running on 5008')
        await asyncio.sleep(3)

asyncio.run(main())