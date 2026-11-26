"""
AeroBrowse + OpenAI / Anthropic Tool Calling Example
=====================================================
Provider-neutral tool schema example; consult your provider documentation.
"""

from aerobrowse import AeroBrowser

browser = AeroBrowser()

# Function calling schema for OpenAI / LiteLLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "browse_url",
            "description": "Fetch a web page, extract bounded semantic content, and return clean Markdown with numbered action IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to visit"},
                    "force_fidelity": {"type": "boolean", "description": "Set true for dynamic pages on a supported isolated Linux host"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click a live element by its generation-scoped action ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string", "description": "Live action ID"},
                    "generation": {"type": "string", "description": "Active snapshot generation"}
                },
                "required": ["action_id", "generation"]
            }
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    if name == "browse_url":
        res = browser.fetch(args["url"], force_fidelity=args.get("force_fidelity", False))
        return str(res)
    elif name == "click_element":
        res = browser.click(args["action_id"], args["generation"])
        return str(res)
    return "Unknown tool"

if __name__ == "__main__":
    print("Executing OpenAI Tool: browse_url on Hacker News...")
    out = execute_tool("browse_url", {"url": "https://news.ycombinator.com"})
    print(out[:400])
