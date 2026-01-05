"""WebSocket for real-time updates."""
import asyncio
import json
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()


async def broadcast_update(event_type: str, data: dict):
    """Broadcast update to all connected clients."""
    logger.info(f"Broadcasting {event_type} to {len(active_connections)} connections")
    
    if not active_connections:
        logger.info("No active connections to broadcast to")
        return
    
    message = json.dumps({
        "type": event_type,
        "data": data,
    })
    
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_text(message)
            logger.info(f"Sent {event_type} to connection")
        except Exception as e:
            logger.warning(f"Failed to send to websocket: {e}")
            disconnected.add(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.discard(conn)


def broadcast_update_sync(event_type: str, data: dict):
    """Synchronous wrapper for broadcast_update - schedules the broadcast."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(broadcast_update(event_type, data))
        else:
            loop.run_until_complete(broadcast_update(event_type, data))
    except RuntimeError:
        # No event loop, create new one
        asyncio.run(broadcast_update(event_type, data))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"WebSocket connected. Total connections: {len(active_connections)}")
    
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(active_connections)}")
