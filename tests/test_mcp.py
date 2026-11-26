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
                "browser_tabs",
                "browser_new_tab",
                "browser_switch_tab",
                "browser_close_tab",
                "browser_back",
                "browser_forward",
            } <= tools.keys()
            assert "generation" in tools["browser_click"].inputSchema["required"]
            assert "tab_id" in tools["browser_switch_tab"].inputSchema["required"]
            assert (
                tools["browser_new_tab"].inputSchema["properties"]["url"]["maxLength"]
                == 8192
            )
            response = await a.call_tool(
                "browser_navigate", {"url": "http://127.0.0.1"}
            )
            assert response.data["error"]["code"] == "BLOCKED_DESTINATION"
            sid = response.data["session_id"]
            denied = await b.call_tool("browser_snapshot", {"session_id": sid})
            assert denied.data["error"]["code"] == "SESSION_NOT_FOUND"
            for operation in ("browser_tabs", "browser_back", "browser_forward"):
                denied = await b.call_tool(operation, {"session_id": sid})
                assert denied.data["error"]["code"] == "SESSION_NOT_FOUND"
            for operation in ("browser_switch_tab", "browser_close_tab"):
                denied = await b.call_tool(
                    operation, {"session_id": sid, "tab_id": "f" * 32}
                )
                assert denied.data["error"]["code"] == "SESSION_NOT_FOUND"
            own = await a.call_tool("browser_snapshot", {"session_id": sid})
            assert own.data["error"]["code"] == "NO_ACTIVE_PAGE"
            closed = await a.call_tool("browser_close", {"session_id": sid})
            assert closed.data["success"]
        await sessions.close_all()

    asyncio.run(run())
