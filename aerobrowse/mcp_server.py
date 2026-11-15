"""
AeroBrowse Model Context Protocol (MCP) Server
Allows Claude Desktop, Cursor, Antigravity, and AI Agents to browse
the web with 90% fewer tokens and zero resource bloat.
"""

import sys
import base64
from fastmcp import FastMCP
from aerobrowse.engine import AeroBrowser

mcp = FastMCP("AeroBrowse")
browser_instance = None

def get_browser() -> AeroBrowser:
    global browser_instance
    if browser_instance is None:
        browser_instance = AeroBrowser()
    return browser_instance


@mcp.tool()
def browser_navigate(url: str, force_js: bool = False) -> str:
    """
    Navigate to a URL and return token-dense Markdown along with an actionable element map.
    Use this to read documentation, news, search results, or interactive web pages.
    """
    b = get_browser()
    res = b.fetch(url, force_fidelity=force_js)

    output = []
    output.append(f"# {res.get('title', 'Untitled')}")
    output.append(f"**URL**: {res.get('url', url)}")
    output.append(f"**Engine**: {res.get('engine', 'auto').upper()} ({res.get('elapsed_ms', 0)}ms, {res.get('reduction_pct', 0)}% token reduction)\n")
    output.append("## Content\n")
    output.append(res.get("markdown", "No content extracted."))

    actions = res.get("actions", [])
    if actions:
        output.append("\n## Interactive Elements (Use Action ID to Click/Fill)")
        for a in actions[:40]:  # Cap to first 40 for token efficiency
            tag = a.get("tag")
            aid = a.get("id")
            label = a.get("label")
            href = f" (href: {a['href']})" if a.get("href") else ""
            output.append(f"[{aid}] <{tag}> {label}{href}")

    return "\n".join(output)


@mcp.tool()
def browser_click(action_id: str) -> str:
    """
    Click an interactive element on the current page using its Action ID (e.g. '1', '2').
    """
    b = get_browser()
    res = b.click(action_id)
    if res.get("success"):
        snap = b.snapshot()
        return f"Successfully clicked element [{action_id}]. New page title: {snap.get('title')}"
    return f"Failed to click element [{action_id}]: {res.get('error')}"


@mcp.tool()
def browser_fill(action_id: str, value: str) -> str:
    """
    Fill an input field or search bar on the current page using its Action ID and text value.
    """
    b = get_browser()
    res = b.fill(action_id, value)
    if res.get("success"):
        return f"Successfully typed '{value}' into field [{action_id}]."
    return f"Failed to fill field [{action_id}]: {res.get('error')}"


@mcp.tool()
def browser_snapshot() -> str:
    """
    Capture the latest snapshot and action map of the currently active page.
    """
    b = get_browser()
    snap = b.snapshot()
    return f"# {snap.get('title')}\n\n{snap.get('markdown')}"


@mcp.tool()
def browser_screenshot() -> str:
    """
    Take a visual screenshot of the current page (returned as base64 PNG).
    """
    b = get_browser()
    png_bytes = b.screenshot()
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@mcp.tool()
def browser_close() -> str:
    """
    Close the current browser session and release all memory.
    """
    global browser_instance
    if browser_instance:
        browser_instance.close()
        browser_instance = None
    return "AeroBrowse session closed."


def run_mcp():
    mcp.run()

if __name__ == "__main__":
    run_mcp()
