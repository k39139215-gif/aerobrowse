"""Bounded newline-delimited UTF-8 MCP stdio, before SDK deserialization.

The official SDK handles protocol negotiation, methods, cancellation and tool schemas.
This boundary limits framing/JSON shape and keeps active request IDs unique.
"""

from __future__ import annotations

import json
import math
import os
import queue
import sys
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, BinaryIO, Protocol, cast

import anyio
from mcp import types
from mcp.shared.message import SessionMessage
from pydantic import ValidationError


class BufferedInput(Protocol):
    def fileno(self) -> int: ...


@dataclass(frozen=True)
class TransportLimits:
    frame_bytes: int = 131072
    depth: int = 32
    nodes: int = 8192
    container_items: int = 2048
    string_chars: int = 65536
    in_flight: int = 64
    frame_seconds: float = 10.0
    output_bytes: int = 8 * 1024 * 1024
    output_seconds: float = 10.0


class FrameError(ValueError):
    """A public fixed error with no input/stack details."""

    def __init__(self, code: int, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def _check_nesting(text: str, limit: int) -> None:
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > limit:
                raise FrameError(-32600, "JSON nesting limit exceeded")
        elif char in "]}":
            depth -= 1


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FrameError(-32600, "Duplicate JSON object key")
        result[key] = value
    return result


def _check_shape(value: Any, limits: TransportLimits) -> None:
    remaining = [value]
    nodes = 0
    while remaining:
        current = remaining.pop()
        nodes += 1
        if nodes > limits.nodes:
            raise FrameError(-32600, "JSON node limit exceeded")
        if isinstance(current, str):
            if len(current) > limits.string_chars or any(
                0xD800 <= ord(c) <= 0xDFFF for c in current
            ):
                raise FrameError(-32600, "Invalid or oversized JSON string")
        elif isinstance(current, float) and not math.isfinite(current):
            raise FrameError(-32700, "Non-finite JSON number is not permitted")
        elif isinstance(current, (list, dict)):
            if len(current) > limits.container_items:
                raise FrameError(-32600, "JSON container limit exceeded")
            remaining.extend(current)
            if isinstance(current, dict):
                remaining.extend(current.values())


def _bounded_integer(value: str) -> int:
    # Apply the same bound even when the operator disables Python's global digit cap.
    if len(value.lstrip("-")) > 128:
        raise FrameError(-32700, "JSON integer limit exceeded")
    return int(value)


def decode_frame(frame: bytes, limits: TransportLimits) -> dict[str, Any]:
    if len(frame) > limits.frame_bytes:
        raise FrameError(-32600, "MCP frame limit exceeded")
    try:
        text = frame.decode("utf-8", errors="strict")
        _check_nesting(text, limits.depth)
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: _reject_constant(),
            parse_int=_bounded_integer,
        )
    except FrameError:
        raise
    except (ValueError, RecursionError) as exc:
        raise FrameError(-32700, "Invalid UTF-8 JSON") from exc
    _check_shape(value, limits)
    if not isinstance(value, dict):
        raise FrameError(
            -32600, "MCP messages must be JSON objects; batches are not supported"
        )
    return value


def _reject_constant() -> Any:
    raise FrameError(-32700, "Non-finite JSON number is not permitted")


def _known_methods(model: Any) -> set[str]:
    definitions = model.model_json_schema().get("$defs", {})
    return {
        definition["properties"]["method"]["const"]
        for definition in definitions.values()
        if "const" in definition.get("properties", {}).get("method", {})
    }


REQUEST_METHODS = _known_methods(types.ClientRequest)
NOTIFICATION_METHODS = _known_methods(types.ClientNotification)


def validate_envelope(value: dict[str, Any]) -> types.JSONRPCMessage:
    try:
        message = types.JSONRPCMessage.model_validate(value)
    except ValidationError as exc:
        raise FrameError(-32600, "Invalid JSON-RPC message") from exc
    root = message.root
    if "id" in value and type(value["id"]) not in {int, str}:
        raise FrameError(-32600, "Invalid JSON-RPC identifier")
    if isinstance(root, types.JSONRPCRequest):
        if set(value) - {"jsonrpc", "id", "method", "params"}:
            raise FrameError(-32600, "Unexpected JSON-RPC envelope fields")
        if root.method not in REQUEST_METHODS:
            raise FrameError(-32601, "Method not found")
        try:
            types.ClientRequest.model_validate(value)
        except ValidationError as exc:
            raise FrameError(-32602, "Invalid method parameters") from exc
    elif isinstance(root, types.JSONRPCNotification):
        if set(value) - {"jsonrpc", "method", "params"}:
            raise FrameError(-32600, "Unexpected JSON-RPC envelope fields")
        if root.method in REQUEST_METHODS:
            raise FrameError(-32600, "Request method requires an identifier")
        if root.method in NOTIFICATION_METHODS:
            try:
                types.ClientNotification.model_validate(value)
            except ValidationError as exc:
                raise FrameError(-32602, "Invalid notification parameters") from exc
    return message


class _InputPump:
    """One bounded daemon reader; a blocked OS pipe never prevents process exit."""

    def __init__(self, incoming: BufferedInput):
        self.chunks: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self.stopping = threading.Event()

        def pump() -> None:
            try:
                while not self.stopping.is_set():
                    # Raw descriptor read avoids holding a BufferedReader lock at interpreter shutdown.
                    chunk = os.read(incoming.fileno(), 4096)
                    while not self.stopping.is_set():
                        try:
                            self.chunks.put(chunk, timeout=0.1)
                            break
                        except queue.Full:
                            continue
                    if not chunk:
                        return
            except (OSError, ValueError):
                self.stopping.set()

        self.thread = threading.Thread(target=pump, daemon=True, name="aero-stdio")
        self.thread.start()

    async def receive(self) -> bytes:
        while True:
            try:
                return self.chunks.get_nowait()
            except queue.Empty:
                if self.stopping.is_set():
                    return b""
                await anyio.sleep(0.01)


@asynccontextmanager
async def bounded_stdio_server(
    stdin: BufferedInput | None = None,
    stdout: BinaryIO | None = None,
    limits: TransportLimits | None = None,
):
    limits = limits or TransportLimits()
    incoming = stdin if stdin is not None else cast(BufferedInput, sys.stdin.buffer)
    outgoing = stdout if stdout is not None else sys.stdout.buffer
    reader_tx, reader_rx = anyio.create_memory_object_stream[
        SessionMessage | Exception
    ](0)
    writer_tx, writer_rx = anyio.create_memory_object_stream[SessionMessage](0)
    output_lock = anyio.Lock()
    pump = _InputPump(incoming)
    active: set[tuple[type, int | str]] = set()

    async def write(payload: dict[str, Any]) -> None:
        encoded = (
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
        )
        if len(encoded) > limits.output_bytes:
            raise FrameError(-32603, "MCP response limit exceeded")
        async with output_lock:
            complete = threading.Event()
            failures: list[Exception] = []

            def flush() -> None:
                try:
                    view = memoryview(encoded)
                    while view:
                        written = os.write(outgoing.fileno(), view)
                        if written <= 0:
                            raise OSError("MCP output pipe closed")
                        view = view[written:]
                except (OSError, ValueError) as exc:
                    failures.append(exc)
                finally:
                    complete.set()

            threading.Thread(target=flush, daemon=True, name="aero-stdout").start()
            with anyio.move_on_after(limits.output_seconds) as scope:
                while not complete.is_set():
                    await anyio.sleep(0.01)
            if scope.cancel_called or failures:
                group.cancel_scope.cancel()
                await anyio.lowlevel.checkpoint()

    async def error(exc: FrameError, request_id: Any = None) -> None:
        await write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": exc.message},
            }
        )

    async def process_frame(frame: bytes) -> bool:
        request_id: int | str | None = None
        try:
            value = decode_frame(frame, limits)
            raw_id = value.get("id")
            if type(raw_id) in {int, str}:
                request_id = raw_id
            message = validate_envelope(value)
            root = message.root
            if (
                isinstance(root, types.JSONRPCNotification)
                and root.method not in NOTIFICATION_METHODS
            ):
                return (
                    True  # Unknown MCP notifications must be ignored, never answered.
                )
            if isinstance(root, types.JSONRPCRequest):
                key = (type(root.id), root.id)
                if key in active:
                    return False  # Close instead of overwriting an SDK responder.
                if len(active) >= limits.in_flight:
                    await error(
                        FrameError(-32000, "MCP in-flight request limit exceeded"),
                        root.id,
                    )
                    return True
                active.add(key)
            await reader_tx.send(SessionMessage(message))
        except FrameError as exc:
            await error(exc, request_id)
        return True

    async def read_chunk(deadline: float | None) -> bytes:
        if deadline is None:
            return await pump.receive()
        remaining = deadline - anyio.current_time()
        if remaining <= 0:
            raise FrameError(-32600, "MCP partial frame deadline exceeded")
        with anyio.move_on_after(remaining) as scope:
            chunk = await pump.receive()
        if scope.cancel_called:
            raise FrameError(-32600, "MCP partial frame deadline exceeded")
        return chunk

    async def drain_frames(buffer: bytearray) -> bool:
        while b"\n" in buffer:
            split = buffer.index(b"\n")
            frame = bytes(buffer[:split])
            del buffer[: split + 1]
            if not await process_frame(frame):
                return False
        return True

    async def stdin_reader() -> None:
        buffer = bytearray()
        deadline: float | None = None
        async with reader_tx:
            while True:
                try:
                    chunk = await read_chunk(deadline)
                    if not chunk:
                        if buffer:
                            await error(FrameError(-32700, "Incomplete MCP frame"))
                        return
                    buffer.extend(chunk)
                    if deadline is None:
                        deadline = anyio.current_time() + limits.frame_seconds
                    if not await drain_frames(buffer):
                        return
                    if len(buffer) > limits.frame_bytes:
                        raise FrameError(-32600, "MCP frame limit exceeded")
                    if not buffer:
                        deadline = None
                    elif b"\n" in chunk:
                        deadline = anyio.current_time() + limits.frame_seconds
                except FrameError as exc:
                    await error(exc)
                    return

    async def stdout_writer() -> None:
        async with writer_rx:
            async for session_message in writer_rx:
                root = session_message.message.root
                payload = session_message.message.model_dump(
                    by_alias=True, exclude_none=True
                )
                try:
                    await write(payload)
                except FrameError as exc:
                    await error(
                        exc,
                        root.id
                        if isinstance(root, (types.JSONRPCResponse, types.JSONRPCError))
                        else None,
                    )
                finally:
                    if isinstance(root, (types.JSONRPCResponse, types.JSONRPCError)):
                        active.discard((type(root.id), root.id))

    async def read_until_disconnect() -> None:
        try:
            await stdin_reader()
        finally:
            group.cancel_scope.cancel()

    async with anyio.create_task_group() as group:
        group.start_soon(read_until_disconnect)
        group.start_soon(stdout_writer)
        try:
            yield reader_rx, writer_tx
        finally:
            pump.stopping.set()
            group.cancel_scope.cancel()
