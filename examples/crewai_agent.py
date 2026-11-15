"""
AeroBrowse + CrewAI Integration Example
========================================
Drop-in custom tool for CrewAI research agents.
"""

from crewai.tools import tool
from aerobrowse import AeroBrowser

browser = AeroBrowser()

@tool("AeroBrowse Web Reader")
def read_web_page(url: str) -> str:
    """
    Reads a web page and returns compact, token-optimized Markdown.
    Cuts LLM context consumption by up to 92% compared to raw HTML.
    """
    res = browser.fetch(url)
    return res["markdown"]

if __name__ == "__main__":
    print("CrewAI Tool ready with AeroBrowser.")
    output = read_web_page("https://en.wikipedia.org/wiki/Artificial_intelligence")
    print(f"Sample output ({len(output)} chars):\n{output[:400]}")
