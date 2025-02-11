# server.py
import asyncio
import json
import uuid
from aiohttp import web

# Dictionary to store connected clients: client_id -> WebSocketResponse
clients = {}

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Assign a unique ID to this client
    client_id = str(uuid.uuid4())
    clients[client_id] = ws
    print(f'New client connected: {client_id}')

    # Send the client its ID
    await ws.send_json({"type": "id", "id": client_id})

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "Invalid JSON."})
                    continue

                # Expected message format:
                # { "type": "signal", "to": "<target_client_id>", "data": { ... } }
                if data.get("type") == "signal":
                    target_id = data.get("to")
                    if target_id in clients:
                        forward = {
                            "type": "signal",
                            "from": client_id,
                            "data": data.get("data")
                        }
                        await clients[target_id].send_json(forward)
                        print(f"Forwarded message from {client_id} to {target_id}")
                    else:
                        await ws.send_json({"type": "error", "message": "Target client not found."})
                else:
                    await ws.send_json({"type": "error", "message": "Unknown message type."})
            elif msg.type == web.WSMsgType.ERROR:
                print(f'WebSocket connection closed with exception {ws.exception()}')
    except Exception as e:
        print("Exception:", e)
    finally:
        print(f"Client disconnected: {client_id}")
        # Remove the client from our list when it disconnects.
        if client_id in clients:
            del clients[client_id]
    return ws

app = web.Application()
app.add_routes([web.get('/ws', websocket_handler)])

if __name__ == '__main__':
    web.run_app(app, port=8080)
