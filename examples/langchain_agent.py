"""
AeroBrowse + LangChain Integration Example
===========================================
Drop-in tool for LangChain and LangGraph agents with 90% token reduction.
"""

from langchain.tools import tool
from aerobrowse import AeroBrowser

browser = AeroBrowser()

@tool
def browse_web(url: str, force_fidelity: bool = False) -> str:
    """
    Fetches any web page, strips 90% HTML noise, and returns clean Markdown 
    with numbered Action IDs ([1], [2]) for LLM reasoning.
    """
    res = browser.fetch(url, force_fidelity=force_fidelity)
    return f"Title: {res['title']}\nURL: {res['url']}\nToken Reduction: {res['reduction_pct']}%\n\n{res['markdown']}"

if __name__ == "__main__":
    url = "https://news.ycombinator.com"
    print(f"Fetching {url} via LangChain tool...")
    content = browse_web.invoke({"url": url})
    print(content[:600])
