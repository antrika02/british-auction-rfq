"""Passes live messages from the API to open WebSocket connections.

Right now it lives inside one server process. To run many servers, you would
swap this class for one that uses Redis pub/sub. The publish() and
subscribe() functions would stay exactly the same.
"""

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager


class InMemoryBroker:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, channel: str, message: dict) -> None:
        for queue in list(self._subs.get(channel, ())):
            if queue.full():  # a slow browser must never slow everyone else down
                try:
                    queue.get_nowait()  # drop its oldest message
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)

    @asynccontextmanager
    async def subscribe(self, channel: str):
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[channel].add(queue)
        try:
            yield queue
        finally:
            self._subs[channel].discard(queue)
            if not self._subs[channel]:
                self._subs.pop(channel, None)


broker = InMemoryBroker()
