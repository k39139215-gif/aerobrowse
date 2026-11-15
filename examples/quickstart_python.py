"""
AeroBrowse Quickstart - 5 Lines of Python
"""
import asyncio
from aerobrowse import AeroEngine

async def run():
    async with AeroEngine() as browser:
        page = await browser.navigate("https://github.com/trending")
        print(f"Tokens: {page.token_count} | Mode: {page.mode}")
        print(page.markdown[:300])

if __name__ == "__main__":
    asyncio.run(run())
