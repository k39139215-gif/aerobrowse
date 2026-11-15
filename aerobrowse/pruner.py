"""
AeroBrowse Semantic Token Optimizer & Actionable Graph Extractor
Reduces 50,000+ tokens of raw HTML slop into clean, token-dense Markdown
and an indexed Actionable Accessibility Tree for AI Agents.
"""

import re
from bs4 import BeautifulSoup, Comment
from typing import Dict, Any, List, Tuple


class SemanticPruner:
    """
    Parses messy raw HTML and generates:
    1. Clean, LLM-ready Markdown content.
    2. Indexed Interactive Map (Buttons, Inputs, Links) with unique Action IDs.
    3. Token & Byte saving metrics.
    """

    UNWANTED_TAGS = {
        "script", "style", "noscript", "svg", "path", "meta", "link",
        "header-nav", "ad", "iframe", "embed", "object"
    }

    def __init__(self):
        pass

    def prune(self, html: str, base_url: str = "") -> Dict[str, Any]:
        if not html:
            return {
                "markdown": "",
                "actions": [],
                "title": "",
                "original_chars": 0,
                "pruned_chars": 0,
                "reduction_pct": 0.0
            }

        original_chars = len(html)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Page Title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled Page"

        # 2. Remove unwanted tags and comments
        for element in soup.find_all(string=lambda text: isinstance(text, Comment)):
            element.extract()

        for tag in self.UNWANTED_TAGS:
            for s in soup.find_all(tag):
                s.decompose()

        # Remove base64 data URIs from images to avoid token explosion
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src.startswith("data:"):
                img["src"] = "[inline-image]"

        # 3. Build Actionable Element Map
        actions: List[Dict[str, Any]] = []
        action_counter = 1

        # Interactive selectors: a, button, input, textarea, select, [role="button"]
        interactive_tags = soup.find_all(["button", "a", "input", "textarea", "select", "details"])
        for tag in interactive_tags:
            tag_name = tag.name
            tag_type = tag.get("type", "").lower()
            tag_text = tag.get_text(strip=True)
            aria_label = tag.get("aria-label", "") or tag.get("placeholder", "") or tag.get("title", "")
            label = (tag_text or aria_label)[:60].strip()

            href = tag.get("href", "")
            value = tag.get("value", "")

            # Filter out empty hidden tags or utility links
            if tag_name == "input" and tag_type in ("hidden", "submit"):
                continue

            if not label and not href and not value:
                continue

            action_id = action_counter
            action_counter += 1

            # Tag the element directly in soup with data-aero-id
            tag["data-aero-id"] = str(action_id)

            action_info = {
                "id": action_id,
                "tag": tag_name,
                "type": tag_type if tag_type else None,
                "label": label or (href if tag_name == "a" else f"<{tag_name}>"),
                "href": href if href else None,
                "name": tag.get("name"),
                "id_attr": tag.get("id"),
            }
            actions.append(action_info)

        # 4. Generate Clean Markdown
        markdown = self._soup_to_markdown(soup)

        pruned_chars = len(markdown)
        reduction_pct = round((1.0 - (pruned_chars / max(1, original_chars))) * 100, 1)

        return {
            "title": title,
            "markdown": markdown,
            "actions": actions,
            "original_chars": original_chars,
            "pruned_chars": pruned_chars,
            "reduction_pct": max(0.0, reduction_pct)
        }

    def _soup_to_markdown(self, soup: BeautifulSoup) -> str:
        """Converts cleaned DOM to clean, dense GitHub-style Markdown."""
        lines = []

        # Find main content container if present to reduce navigation noise
        main_content = soup.find(["main", "article"]) or soup.find(id=re.compile(r"content|main|article", re.I)) or soup.body or soup

        for elem in main_content.descendants:
            if elem.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(elem.name[1])
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"\n{'#' * level} {text}\n")
            elif elem.name == "p":
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"{text}\n")
            elif elem.name == "li":
                text = elem.get_text(strip=True)
                if text:
                    lines.append(f"* {text}")
            elif elem.name == "pre" or elem.name == "code":
                if elem.parent.name != "pre":
                    code_text = elem.get_text()
                    if len(code_text.splitlines()) > 1:
                        lines.append(f"\n```\n{code_text.strip()}\n```\n")
            elif elem.name == "table":
                # Convert simple table
                table_md = self._table_to_markdown(elem)
                if table_md:
                    lines.append(table_md)

        raw_md = "\n".join(lines)
        # Collapse multiple empty newlines
        clean_md = re.sub(r"\n{3,}", "\n\n", raw_md).strip()

        # Fallback if sparse
        if len(clean_md) < 60:
            clean_md = main_content.get_text(separator="\n", strip=True)

        return clean_md

    def _table_to_markdown(self, table_tag) -> str:
        rows = []
        for tr in table_tag.find_all("tr"):
            cells = [c.get_text(strip=True).replace("|", "/") for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        if not rows:
            return ""

        col_count = max(len(r) for r in rows)
        out = []
        for i, row in enumerate(rows):
            # Pad row
            padded = row + [""] * (col_count - len(row))
            out.append("| " + " | ".join(padded) + " |")
            if i == 0:
                out.append("| " + " | ".join(["---"] * col_count) + " |")
        return "\n" + "\n".join(out) + "\n"
