"""
AeroBrowse + LangChain Integration Example
===========================================
Drop-in tool for LangChain and LangGraph agents with 90% token reduction.
"""

import asyncio
from aerobrowse import AeroEngine

async def main():
    engine = AeroEngine()
    
    # 1. Fetch web page in Turbo mode (sub-100ms, ~50MB RAM)
    url = "https://news.ycombinator.com"
    print(f"Fetching {url} with AeroBrowse...")
    
    result = await engine.navigate(url)
    
    print("\n" + "=" * 50)
    print(f"URL: {result.url}")
    print(f"Mode Used: {result.mode}")
    print(f"Latency: {result.latency_ms:.1f}ms")
    print(f"Estimated Tokens: {result.token_count}")
    print(f"Interactive Elements Detected: {len(result.action_elements)}")
    print("=" * 50)
    print("\nClean LLM-Ready Markdown Output (First 500 chars):\n")
    print(result.markdown[:500] + "\n...")

if __name__ == "__main__":
    asyncio.run(main())
