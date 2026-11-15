"""
AeroBrowse + OpenAI / Anthropic Tool Calling Example
=====================================================
Direct JSON tool schema for GPT-4o, Claude 3.5, and OpenAI Swarm.
"""

from aerobrowse import AeroBrowser

browser = AeroBrowser()

# Function calling schema for OpenAI / LiteLLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Fetch a web page, strip 90% HTML noise, and return clean Markdown with numbered action IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to visit"},
                    "force_fidelity": {"type": "boolean", "description": "Set true for dynamic SPAs or logins"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element by its numeric Action ID [1], [2], etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string", "description": "Action ID of the button or link"}
                },
                "required": ["action_id"]
            }
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    if name == "browse_url":
        res = browser.fetch(args["url"], force_fidelity=args.get("force_fidelity", False))
        return res["markdown"]
    elif name == "click_element":
        res = browser.click(args["action_id"])
        return str(res)
    return "Unknown tool"

if __name__ == "__main__":
    print("Executing OpenAI Tool: browse_url on Hacker News...")
    out = execute_tool("browse_url", {"url": "https://news.ycombinator.com"})
    print(out[:400])
