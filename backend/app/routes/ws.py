import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..broker import broker

router = APIRouter()


async def _stream(websocket: WebSocket, channel: str) -> None:
    await websocket.accept()
    async with broker.subscribe(channel) as queue:

        async def forward() -> None:
            while True:
                await websocket.send_json(await queue.get())

        sender = asyncio.create_task(forward())
        try:
            while True:
                await websocket.receive_text()  # keeps the connection open
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()


@router.websocket("/ws/rfqs")
async def watch_all(websocket: WebSocket):
    """For the listing page: told whenever any auction changes."""
    await _stream(websocket, "rfqs")


@router.websocket("/ws/rfqs/{rfq_id}")
async def watch_one(websocket: WebSocket, rfq_id: int):
    """For the details page: told whenever this auction changes."""
    await _stream(websocket, f"rfq:{rfq_id}")
