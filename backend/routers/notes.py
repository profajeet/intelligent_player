import json
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from models.schemas import NoteDelta, NoteOperation
from services.storage_service import get_note, save_note

router = APIRouter()

# video_id → set of connected WebSocket clients
_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    async def connect(self, websocket: WebSocket, video_id: str):
        await websocket.accept()
        _connections.setdefault(video_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, video_id: str):
        if video_id in _connections:
            _connections[video_id].discard(websocket)
            if not _connections[video_id]:
                del _connections[video_id]

    async def broadcast(self, video_id: str, message: dict, exclude: WebSocket = None):
        for ws in list(_connections.get(video_id, [])):
            if ws is not exclude:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/notes/{video_id}")
async def notes_ws(websocket: WebSocket, video_id: str):
    await manager.connect(websocket, video_id)

    # Send the current note content on connect
    current_content = await get_note(video_id)
    await websocket.send_json({
        "op":      NoteOperation.FULL,
        "video_id": video_id,
        "content": current_content,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data   = json.loads(raw)
                delta  = NoteDelta(**data)
            except Exception as e:
                await websocket.send_json({"error": f"Invalid payload: {e}"})
                continue

            now = datetime.now(timezone.utc)

            # Handle each operation type
            if delta.op in (NoteOperation.INSERT, NoteOperation.UPDATE, NoteOperation.FULL):
                if delta.content is not None:
                    await save_note(video_id, delta.content)

            elif delta.op == NoteOperation.APPEND_SCREENSHOT:
                # Append screenshot markdown to existing note
                existing = await get_note(video_id)
                ts_label = f" *(at {_fmt_time(delta.timestamp)})*" if delta.timestamp else ""
                screenshot_md = f"\n\n![screenshot{ts_label}]({delta.screenshot_url})\n"
                new_content   = existing + screenshot_md
                await save_note(video_id, new_content)
                delta.content = new_content   # propagate full updated content

            response = {
                "op":       delta.op,
                "video_id": video_id,
                "content":  delta.content,
                "screenshot_url": delta.screenshot_url,
                "saved_at": now.isoformat(),
            }

            # Echo back to sender (confirmation)
            await websocket.send_json(response)

            # Broadcast to all other clients on the same video
            await manager.broadcast(video_id, response, exclude=websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, video_id)


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"
