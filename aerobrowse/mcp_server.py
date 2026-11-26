"""MCP stdio tools with explicit owned browser sessions and safe errors."""

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

from aerobrowse.errors import AeroError
from aerobrowse.sessions import SessionManager

sessions = SessionManager()


@asynccontextmanager
async def lifespan(server: FastMCP):
    async def sweep():
        while True:
            await asyncio.sleep(10)
            await sessions.expire()

    task = asyncio.create_task(sweep())
    try:
        yield {}
    finally:
        task.cancel()
        # Collect only the explicitly cancelled child; cancellation of this parent propagates.
        await asyncio.gather(task, return_exceptions=True)
        await sessions.close_all()


mcp = FastMCP(
    "AeroBrowse",
    mask_error_details=True,
    strict_input_validation=True,
    lifespan=lifespan,
)
SessionID = Annotated[str, Field(min_length=32, max_length=128)]
ActionID = Annotated[str, Field(pattern=r"^[0-9a-f]{32}:[1-9][0-9]{0,5}$")]
Generation = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


@mcp.tool()
async def browser_navigate(
    url: Annotated[str, Field(min_length=1, max_length=8192)],
    ctx: Context,
    force_js: bool = False,
    session_id: SessionID | None = None,
) -> dict[str, Any]:
    """Navigate; omit session_id to create an owned session, then reuse the returned ID."""
    try:
        sid = session_id or await sessions.create(ctx.session_id)
        return await sessions.call(
            ctx.session_id, sid, "navigate", url, force_fidelity=force_js
        )
    except AeroError as exc:
        return exc.result()


@mcp.tool()
async def browser_snapshot(session_id: SessionID, ctx: Context) -> dict[str, Any]:
    """Return the active page and fresh live action generation."""
    return await sessions.call(ctx.session_id, session_id, "snapshot")


@mcp.tool()
async def browser_click(
    session_id: SessionID, action_id: ActionID, generation: Generation, ctx: Context
) -> dict[str, Any]:
    """Click a live action from the specified snapshot generation."""
    return await sessions.call(
        ctx.session_id, session_id, "click", action_id, generation=generation
    )


@mcp.tool()
async def browser_fill(
    session_id: SessionID,
    action_id: ActionID,
    generation: Generation,
    value: Annotated[str, Field(max_length=65536)],
    ctx: Context,
) -> dict[str, Any]:
    """Fill a live field. Values are not echoed or logged."""
    return await sessions.call(
        ctx.session_id, session_id, "fill", action_id, value, generation=generation
    )


@mcp.tool()
async def browser_select(
    session_id: SessionID,
    action_id: ActionID,
    generation: Generation,
    value: Annotated[str, Field(max_length=8192)],
    ctx: Context,
) -> dict[str, Any]:
    """Select an option by value on a live select control."""
    return await sessions.call(
        ctx.session_id, session_id, "select", action_id, value, generation=generation
    )


@mcp.tool()
async def browser_check(
    session_id: SessionID,
    action_id: ActionID,
    generation: Generation,
    checked: bool,
    ctx: Context,
) -> dict[str, Any]:
    """Check or uncheck a live checkbox."""
    return await sessions.call(
        ctx.session_id, session_id, "perform", "check", action_id, checked, generation
    )


@mcp.tool()
async def browser_press(
    session_id: SessionID,
    action_id: ActionID,
    generation: Generation,
    key: Annotated[str, Field(max_length=64)],
    ctx: Context,
) -> dict[str, Any]:
    """Send a keyboard key to a live element."""
    return await sessions.call(
        ctx.session_id, session_id, "perform", "press", action_id, key, generation
    )


@mcp.tool()
async def browser_scroll(
    session_id: SessionID,
    ctx: Context,
    x: Annotated[int, Field(ge=-10000, le=10000)] = 0,
    y: Annotated[int, Field(ge=-10000, le=10000)] = 600,
) -> dict[str, Any]:
    """Scroll the active live page by bounded pixels."""
    return await sessions.call(ctx.session_id, session_id, "scroll", x, y)


@mcp.tool()
async def browser_wait(
    session_id: SessionID,
    action_id: ActionID,
    generation: Generation,
    ctx: Context,
    timeout_ms: Annotated[int, Field(ge=1, le=30000)] = 5000,
) -> dict[str, Any]:
    """Wait for an existing live element; arbitrary CSS selectors are not accepted."""
    return await sessions.call(
        ctx.session_id, session_id, "wait", action_id, generation, timeout_ms
    )


@mcp.tool()
async def browser_screenshot(session_id: SessionID, ctx: Context) -> dict[str, Any]:
    """Return bounded base64 PNG; screenshots can contain sensitive page content."""
    return await sessions.call(ctx.session_id, session_id, "screenshot")


@mcp.tool()
async def browser_close(session_id: SessionID, ctx: Context) -> dict[str, Any]:
    """Close only this client's specified session."""
    return await sessions.close(ctx.session_id, session_id)


async def _run_bounded_stdio() -> None:
    from fastmcp.server.context import reset_transport, set_transport
    from mcp.server.lowlevel import NotificationOptions

    from aerobrowse.mcp_transport import bounded_stdio_server

    token = set_transport("stdio")
    try:
        async with (
            mcp._lifespan_manager(),
            bounded_stdio_server() as (read_stream, write_stream),
        ):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(
                    notification_options=NotificationOptions(tools_changed=True)
                ),
            )
    finally:
        reset_transport(token)


def run_mcp() -> None:
    asyncio.run(_run_bounded_stdio())


if __name__ == "__main__":
    run_mcp()
