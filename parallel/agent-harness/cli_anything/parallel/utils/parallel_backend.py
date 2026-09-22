"""Own MCP lifecycle, bounded I/O, and result validation for the free endpoint."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from importlib.metadata import version

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ENDPOINT = "https://search.parallel.ai/mcp"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
DEADLINE_SECONDS = 60


class BackendError(Exception):
    """A failed request, distinct from a successful empty result."""


class _BoundedStream(httpx.AsyncByteStream):
    def __init__(self, stream, failure):
        self.stream = stream
        self.failure = failure

    async def __aiter__(self):
        total = 0
        async for chunk in self.stream:
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                error = BackendError("MCP response exceeds the 2 MiB limit")
                if not self.failure.done():
                    self.failure.set_result(error)
                raise error
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


@asynccontextmanager
async def _bounded_client():
    failure = asyncio.get_running_loop().create_future()

    async def bound_response(response):
        # Reject redirects before another host can receive queries or context.
        response.raise_for_status()
        if response.headers.get("content-encoding", "identity") != "identity":
            error = BackendError(
                "Unexpected compressed MCP response; cannot enforce the response bound"
            )
            if not failure.done():
                failure.set_result(error)
            raise error
        response.stream = _BoundedStream(response.stream, failure)

    async def watch_failure():
        # The SDK can swallow stream exceptions. Cancel the entire command when
        # a response violates our bounds, independently of its JSON/SSE parser.
        raise await failure

    async with asyncio.TaskGroup() as tasks:
        watcher = tasks.create_task(watch_failure())
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=False,
                headers={"Accept-Encoding": "identity"},
                event_hooks={"response": [bound_response]},
            ) as client:
                yield client
        finally:
            watcher.cancel()


def _decode(result):
    if result.isError:
        detail = " ".join(b.text for b in result.content if b.type == "text")
        raise BackendError("MCP tool error: " + detail[:1000])
    payload = result.structuredContent
    if payload is None:
        blocks = [b.text for b in result.content if b.type == "text"]
        if len(blocks) != 1:
            raise BackendError("Expected one JSON tool result")
        try:
            payload = json.loads(blocks[0])
        except (ValueError, TypeError) as exc:
            raise BackendError("Invalid JSON tool result") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise BackendError("Tool result is missing its results array")
    for item in payload["results"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("url"), str)
            or not isinstance(item.get("excerpts"), list)
            or not all(isinstance(text, str) for text in item["excerpts"])
        ):
            raise BackendError("Malformed search/fetch result")
    # Preserve warnings, citations, session ID, full content, and per-URL errors.
    if "errors" in payload and not isinstance(payload["errors"], list):
        raise BackendError("Malformed fetch errors")
    if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_OUTPUT_BYTES:
        raise BackendError(
            "Result exceeds the 1 MiB output limit; request fewer URLs or omit --full-content"
        )
    return payload


async def request(tool, arguments):
    """One bounded MCP connection per command; callers own task session IDs."""
    try:
        async with asyncio.timeout(DEADLINE_SECONDS):
            async with _bounded_client() as client:
                # Identify the project for aggregate free MCP usage measurement.
                # Retain the HTTP library token; never add user/device identifiers.
                client.headers["User-Agent"] = (
                    f"cli-anything-parallel/{version('cli-anything-parallel')} "
                    + client.headers["User-Agent"]
                )
                async with streamable_http_client(
                    ENDPOINT, http_client=client
                ) as streams:
                    async with ClientSession(
                        streams[0],
                        streams[1],
                        read_timeout_seconds=timedelta(seconds=30),
                    ) as session:
                        await session.initialize()
                        if tool == "tools":
                            names = []
                            cursor = None
                            for _ in range(10):
                                page = await session.list_tools(cursor=cursor)
                                names.extend(t.name for t in page.tools)
                                cursor = page.nextCursor
                                if not cursor:
                                    return {"tools": names}
                            raise BackendError("Tool discovery exceeded 10 pages")
                        return _decode(await session.call_tool(tool, arguments))
    except BackendError:
        raise
    except TimeoutError as exc:
        raise BackendError("Parallel request exceeded the 60-second deadline") from exc
    except Exception as exc:
        # Task-group failures from the SDK can otherwise hide the useful cause.
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise BackendError(f"Parallel request failed: {str(exc)[:1000]}") from exc
