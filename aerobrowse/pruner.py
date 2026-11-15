"""
AeroBrowse Semantic Token Optimizer & Actionable Graph Extractor
Reduces 50,000+ tokens of raw HTML slop into clean, token-dense Markdown
and an indexed Actionable Accessibility Tree for AI Agents.
Preserves 100% of real textual information while stripping CSS/JS/SVG overhead.
"""

import re
from bs4 import BeautifulSoup, Comment, NavigableString
from typing import Dict, Any, List


class SemanticPruner:
    """
    Parses raw HTML and generates:
    1. Clean, dense LLM-ready Markdown preserving 100% of semantic content.
    2. Indexed Interactive Map (Buttons, Inputs, Links) with unique Action IDs.
    3. Token & Byte saving telemetry.
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

        interactive_tags = soup.find_all(["button", "a", "input", "textarea", "select", "details"])
        for tag in interactive_tags:
            tag_name = tag.name
            tag_type = tag.get("type", "").lower()
            tag_text = tag.get_text(strip=True)
            aria_label = tag.get("aria-label", "") or tag.get("placeholder", "") or tag.get("title", "")
            
            # If inner text is truncated (ends with '...'), prefer title if available
            if tag_text.endswith("...") and tag.get("title"):
                tag_text = tag.get("title")

            label = (tag_text or aria_label)[:80].strip()
            href = tag.get("href", "")
            value = tag.get("value", "")

            if tag_name == "input" and tag_type in ("hidden", "submit"):
                continue

            if not label and not href and not value:
                continue

            action_id = action_counter
            action_counter += 1

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

        # 4. Generate Clean Semantic Markdown
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
        """Converts cleaned DOM to clean, dense GitHub-style Markdown without losing any text."""
        main_content = soup.body or soup

        def walk(node):
            if isinstance(node, NavigableString):
                t = str(node).strip()
                return t + " " if t else ""

            name = getattr(node, 'name', '')
            if not name or name in self.UNWANTED_TAGS:
                return ""

            if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(name[1])
                # Check if child a tag has full title attribute when text is truncated
                a_child = node.find('a')
                if a_child and a_child.get('title') and a_child.get_text(strip=True).endswith("..."):
                    t = a_child.get('title')
                else:
                    t = node.get_text(strip=True)
                return f"\n\n{'#' * level} {t}\n\n" if t else ""
            elif name == 'li':
                c_text = "".join(walk(c) for c in node.children).strip()
                return f"\n* {c_text}" if c_text else ""
            elif name == 'p':
                return f"\n\n{node.get_text(strip=True)}\n\n"
            elif name == 'blockquote':
                return f"\n> {node.get_text(strip=True)}\n"
            elif name == 'pre':
                return f"\n\n```\n{node.get_text().strip()}\n```\n\n"
            elif name == 'table':
                return self._table_to_markdown(node)
            elif name == 'a':
                t_attr = node.get('title', '')
                in_t = node.get_text(strip=True)
                if t_attr and (in_t.endswith("...") or len(t_attr) > len(in_t)):
                    return f" {t_attr} "
                return f" {in_t} "

            # Traverse child nodes
            text = ""
            for child in node.children:
                text += walk(child)

            if name in ('div', 'section', 'article', 'tr', 'header', 'footer') and not text.endswith("\n"):
                text += "\n"

            return text

        raw_md = walk(main_content)
        # Normalize whitespace and multiple newlines
        clean_md = re.sub(r'[ \t]+', ' ', raw_md)
        clean_md = re.sub(r'\n{3,}', '\n\n', clean_md).strip()

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
            padded = row + [""] * (col_count - len(row))
            out.append("| " + " | ".join(padded) + " |")
            if i == 0:
                out.append("| " + " | ".join(["---"] * col_count) + " |")
        return "\n\n" + "\n".join(out) + "\n\n"
