"""Prints every live message for an auction. Usage: python scripts/ws_listen.py ws://localhost:8001/ws/rfqs/2"""
import asyncio
import json
import sys

import websockets


async def main(url: str) -> None:
    async with websockets.connect(url) as ws:
        print("connected. Waiting for messages (Ctrl+C to stop)...")
        async for raw in ws:
            msg = json.loads(raw)
            rfq = msg.get("detail", {}).get("rfq") or msg.get("rfq") or {}
            print(f"{msg['type']}: lowest={rfq.get('lowest_bid')} close={rfq.get('bid_close')} status={rfq.get('status')}")


asyncio.run(main(sys.argv[1]))
