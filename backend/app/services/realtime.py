"""In-process pub/sub for WebSocket clients.

Works with a SINGLE API worker only. For several workers, replace with Redis pub/sub.
publish() is thread-safe: the simulator and bots run in worker threads.
"""
import asyncio
import logging

log = logging.getLogger(__name__)


class Hub:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: dict[asyncio.Queue, int] = {}

    def bind(self, loop):
        self.loop = loop

    def subscribe(self, user_id: int) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=500)
        self.clients[q] = user_id
        return q

    def unsubscribe(self, q):
        self.clients.pop(q, None)

    def _deliver(self, msg: dict, user_id: int | None):
        for q, uid in list(self.clients.items()):
            if user_id is not None and uid != user_id:
                continue
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # slow client: drop, the UI re-syncs through REST

    def publish(self, msg: dict, user_id: int | None = None):
        if self.loop is None or self.loop.is_closed():
            return
        try:
            self.loop.call_soon_threadsafe(self._deliver, msg, user_id)
        except RuntimeError:
            pass


hub = Hub()
