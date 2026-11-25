"""Keep an MCP transport and session on their owning task."""

import asyncio
import logging
from concurrent.futures import Future, wait
from contextlib import ExitStack
from typing import Any, Awaitable, Callable

import anyio
from anyio.from_thread import start_blocking_portal
from mcp import ClientSession, StdioServerParameters

log = logging.getLogger(__name__)


class MCPConnection:
    def __init__(self, params: StdioServerParameters, transport_factory, client_factory) -> None:
        self._closing = False
        self._owner_scope: anyio.CancelScope | None = None
        self._ready: Future[ClientSession] = Future()
        # Awaiters can cancel their wait without cancelling this shared future.
        self._ready.set_running_or_notify_cancel()
        with ExitStack() as stack:
            self._portal = stack.enter_context(start_blocking_portal())
            # Cancel unanswered requests before joining the portal thread.
            stack.callback(self._portal.call, self._portal.stop, True)
            self._owner = self._portal.start_task_soon(
                self._serve, params, transport_factory, client_factory,
            )
            self._owner.add_done_callback(self._finish_startup)
            self._stack = stack.pop_all()

    @property
    def starting(self) -> bool:
        return not self._ready.done()

    async def _serve(self, params, transport_factory, client_factory) -> None:
        async with transport_factory(params) as (read, write):
            async with client_factory(read, write) as client:
                # Cancel work inside the contexts so the SDK can still wait
                # for the entire proxy process tree during context exit.
                with anyio.CancelScope() as owner_scope:
                    self._owner_scope = owner_scope
                    if self._closing:
                        return
                    await client.initialize()
                    self._requests = anyio.Lock()
                    self._ready.set_result(client)
                    await anyio.sleep_forever()

    def _finish_startup(self, owner: Future) -> None:
        if not self._ready.done():
            failure = None if owner.cancelled() else owner.exception()
            self._ready.set_exception(failure or RuntimeError("DOMShell connection stopped during startup"))

    async def run(self, operation: Callable[[ClientSession], Awaitable[Any]]) -> Any:
        client = await asyncio.wrap_future(self._ready)
        if self._closing:
            raise RuntimeError("DOMShell connection is stopping")
        request = self._portal.start_task_soon(self._run, operation, client)
        try:
            return await asyncio.wrap_future(request)
        except asyncio.CancelledError:
            if self._closing:
                raise RuntimeError("DOMShell connection stopped during the request") from None
            raise

    async def _run(
        self, operation: Callable[[ClientSession], Awaitable[Any]], client: ClientSession,
    ) -> Any:
        async with self._requests:
            return await operation(client)

    def close(self) -> None:
        self._closing = True
        try:
            with self._stack:
                self._portal.call(self._stop_owner)
                wait([self._owner])
        except Exception:
            log.warning("Failed to close DOMShell connection", exc_info=True)

    def _stop_owner(self) -> None:
        if self._owner_scope is not None:
            self._owner_scope.cancel()
