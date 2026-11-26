import asyncio

from fastmcp import Client

from aerobrowse.mcp_server import mcp, sessions


def test_protocol_tools_and_cross_client_isolation():
    async def run():
        async with Client(mcp) as a, Client(mcp) as b:
            tools = {t.name: t for t in await a.list_tools()}
            assert {
                "browser_select",
                "browser_scroll",
                "browser_wait",
                "browser_close",
            } <= tools.keys()
            assert "generation" in tools["browser_click"].inputSchema["required"]
            response = await a.call_tool(
                "browser_navigate", {"url": "http://127.0.0.1"}
            )
            assert response.data["error"]["code"] == "BLOCKED_DESTINATION"
            sid = response.data["session_id"]
            denied = await b.call_tool("browser_snapshot", {"session_id": sid})
            assert denied.data["error"]["code"] == "SESSION_NOT_FOUND"
            own = await a.call_tool("browser_snapshot", {"session_id": sid})
            assert own.data["error"]["code"] == "NO_ACTIVE_PAGE"
            closed = await a.call_tool("browser_close", {"session_id": sid})
            assert closed.data["success"]
        await sessions.close_all()

    asyncio.run(run())
