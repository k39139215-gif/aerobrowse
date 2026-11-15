# 🚀 AeroBrowse Launch Playbook: Growth, Stars & Community Guide

This playbook contains battle-tested, high-conversion copy and submission guides to launch AeroBrowse across developer platforms (Hacker News, Reddit, Twitter/X, and Awesome Lists) to attract developers, stars, and real active users.

---

## 1. 🟠 Hacker News (Show HN)

> **Strict Rule**: Hacker News has a hard maximum of **80 characters** for titles. Anything over 80 characters is rejected by HN!  
> Keep titles punchy, factual, and strictly under 70 characters:

### Title Options (Strictly Verified < 70 Characters):
- `Show HN: AeroBrowse – 12MB AI browser that cuts LLM tokens by 88%` *(65 chars — Recommended)*
- `Show HN: AeroBrowse – Featherweight browser engine for AI agents` *(64 chars)*
- `Show HN: AeroBrowse – Dual-engine AI browser in Rust and Python` *(63 chars)*
- `Show HN: We cut LLM web scraping token bills by 88%` *(52 chars)*

### Post Body:
```markdown
Hey HN,

We built AeroBrowse (https://github.com/k39139215-gif/aerobrowse) because running headless Chrome inside AI agent loops (LangChain, CrewAI, AutoGen) has become a nightmare:

1. A single raw HTML page dumps 50,000 to 100,000 tokens of CSS class strings (Tailwind utility spaghetti), inline SVG vector paths, and cookie banners into LLMs. This costs $0.20 to $0.50 per page call and blows through context windows.
2. Standard Chromium instances chew up 300MB–600MB of RAM per tab, causing Out-Of-Memory crashes when agents run parallel crawls on modest VMs.
3. Asking LLMs to invent complex CSS/XPath selectors leads to severe action hallucinations.

AeroBrowse solves this with a dual-engine architecture:
- **Tier-1 Turbo (Rust / Python)**: Direct HTTP client that fetches static HTML in sub-100ms using only 12MB RAM.
- **Tier-2 Fidelity (CDP WebSocket)**: Connects to your existing system Chrome when a dynamic Single Page Application (SPA) is detected, without downloading extra browser runtimes.
- **Semantic AST Pruning**: Recursively strips CSS, SVG icons, and telemetry while preserving 95%+ of visible vocabulary (verified across Quotes, Books, Python.org, and Wikipedia).
- **Set-of-Marks Action Indexing**: Maps all clickable elements to numeric IDs (`[1]`, `[2]`), allowing agents to execute clicks and form fills without CSS selector hallucinations.
- **Native FastMCP**: Exposes stdio tools out-of-the-box for Cursor AI, Claude Desktop, and Antigravity.

We ran a verified 100-page empirical stress test across e-commerce, tech documentation, and forums (results in benchmarks/):
- 100/100 pages crawled in 46.05 seconds (2.2 pages/sec).
- 5.02M raw tokens pruned down to 608k tokens (87.9% reduction).
- $11.05 saved on just those 100 pages alone.

Everything is open source under MIT: https://github.com/k39139215-gif/aerobrowse

Would love your thoughts, benchmark critiques, and feedback on our AST traversal strategy!
```

---

## 2. 🔴 Zero-Karma Reddit Communities (Instant Post Approval)

If you have a fresh account with **0 karma**, subreddits like `r/LocalLLaMA` will automatically remove posts. Instead, post in these high-traffic, karma-friendly communities:

### Community 1: `r/SideProject` (185,000+ Members — Zero Karma Barrier)
- **Title**: `I built a 12MB browser engine that cuts 88% of HTML tokens for AI agents (Open Source)`
- **Flair**: `Showcase` or `Project`
- **Body**:
  ```markdown
  Hey everyone!

  Whenever I fed web pages to AI agents (using Playwright/Puppeteer), 85%+ of the tokens were completely useless CSS classes, SVG paths, and scripts. That burned money and choked context windows.

  So I built **AeroBrowse**: https://github.com/k39139215-gif/aerobrowse

  What it does:
  1. Slashes 88% of token bloat using semantic AST pruning (preserves 95%+ of actual human words).
  2. Runs on only 12MB of RAM in Turbo mode (sub-100ms).
  3. Uses Set-of-Marks (`[1] Click`, `[2] Fill`) so agents never hallucinate CSS selectors.
  4. Native FastMCP support for Cursor AI and Claude Desktop.

  Check out the repo and the 1-click Google Colab demo. Would love your feedback!
  ```

### Community 2: `r/OpenSource` (140,000+ Members — Zero Karma Barrier)
- **Title**: `AeroBrowse – A featherweight, token-pruned browser engine for AI agents (MIT License)`
- **Body**: Focus on open-source MIT license, Rust core, and community benchmarks.

### Community 3: `r/WebScraping` (70,000+ Members — Very Low Barrier)
- **Title**: `Tired of 500MB headless Chrome? We built a 12MB dual-engine scraper that outputs clean Markdown`

### Community 4: `r/AI_Agents` (50,000+ Members)
- **Title**: `Open-source browser tool for LangChain, CrewAI & Cursor AI that cuts token bills by 88%`

---

## 3. 💬 Developer Discord Communities (0 Karma Needed — Instant Reach)

Join these official Discord servers and post in their `#showcase` or `#projects` channels (usually hundreds of AI engineers see this within minutes):

1. **Cursor AI Discord** (`#mcp` or `#showcase`):
   ```
   🚀 Built a native MCP browser server for Cursor: AeroBrowse!
   Cuts 88% of HTML token bloat so your Cursor composer never runs out of context.
   Repo: https://github.com/k39139215-gif/aerobrowse
   ```
2. **LangChain Discord** (`#share-your-project`):
   ```
   Hey builders! Just open-sourced AeroBrowse, a drop-in tool for LangChain agents that browses the web at 12MB RAM and sub-100ms latency with 88% fewer tokens.
   Repo: https://github.com/k39139215-gif/aerobrowse
   ```
3. **CrewAI Discord** (`#showcase`):
   Share the CrewAI integration snippet from `examples/crewai_agent.py`.
4. **FastMCP / Anthropic Discord** (`#community-showcase`):
   Share the FastMCP integration.

---

## 4. 📝 Dev.to & Hashnode Article (Instant Google Ranking & 0 Karma)

Publish a technical post on **Dev.to** (free, instant signup, indexed by Google in 2 hours):
- **Title**: `Why We Built a 12MB Browser Engine for AI Agents (And Cut Token Bills by 88%)`
- **Tags**: `#ai`, `#python`, `#opensource`, `#webdev`
- **Link back**: Include GitHub repo link in the first 2 paragraphs.

---

## 5. ⭐ Awesome-Lists Submissions: Complete Step-by-Step Guide

### What is an "Awesome List"?
An Awesome List is a curated, high-authority GitHub repository with **10,000 to 100,000+ stars**. When someone searches Google for *"best MCP servers"* or *"AI agent browser tools"*, these lists rank #1.

Being listed here guarantees **free, permanent daily traffic and GitHub stars** forever.

### Exactly How to Submit (Step-by-Step Walkthrough):

#### Example: Submitting to `punkpeye/awesome-mcp-servers`

1. **Open the Repository**:
   Go to: https://github.com/punkpeye/awesome-mcp-servers

2. **Fork the Repo**:
   Click the **Fork** button at the top-right of the page (this makes a copy in your personal GitHub account).

3. **Open README.md & Click Edit**:
   - In your forked repo, click on `README.md`.
   - Click the **Pencil Icon (Edit this file)** on the top-right of the file viewer.

4. **Find the Right Category**:
   - Scroll down to the `Browser Automation` or `Web Scraping` category.
   - Maintain alphabetical order and paste this line:
   ```markdown
   - [AeroBrowse](https://github.com/k39139215-gif/aerobrowse) - Featherweight dual-engine AI browser for Cursor & Claude Desktop that slashes LLM tokens by 88% with Set-of-Marks action indexing.
   ```

5. **Commit the Changes**:
   - Scroll to the bottom of the page.
   - In the commit message box, write: `Add AeroBrowse to Browser Automation tools`.
   - Click **Commit changes**.

6. **Create the Pull Request**:
   - Go back to the main page of your fork.
   - GitHub will show a banner saying *"This branch is 1 commit ahead of punkpeye:main"*.
   - Click the green **Contribute** button -> click **Open Pull Request**.
   - Review your change and click **Create Pull Request**.

7. **Repeat for Other Lists**:
   - **`e2b-dev/awesome-ai-agents`**: Category: `Browser & Web Tools`  
     `- [AeroBrowse](https://github.com/k39139215-gif/aerobrowse) - High-performance dual-engine AI browser engine with 88% token reduction and Set-of-Marks interaction.`
   - **`kyrolabs/awesome-langchain`**: Category: `Tools & Scrapers`  
     `- [AeroBrowse](https://github.com/k39139215-gif/aerobrowse) - Drop-in LangChain web browsing tool optimizing token usage and browser RAM.`
   - **`vinta/awesome-python`**: Category: `Web Scraping`  
     `- [AeroBrowse](https://github.com/k39139215-gif/aerobrowse) - Featherweight browser engine for LLMs with semantic AST pruning and CDP automation.`
