"""Bounded semantic HTML extraction. Static actions are informational candidates."""

import re
from typing import Any, ClassVar
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import (
    BeautifulSoup,
    Comment,
    Declaration,
    Doctype,
    NavigableString,
    ProcessingInstruction,
    Tag,
)

from aerobrowse.errors import AeroError
from aerobrowse.security import Limits
from aerobrowse.tokens import measure, measure_output

INTERACTIVE = {"button", "a", "input", "textarea", "select", "summary"}
ROLES = {
    "button",
    "link",
    "textbox",
    "checkbox",
    "combobox",
    "radio",
    "switch",
    "menuitem",
}
EMBEDDED_TAGS = {"iframe", "embed", "object"}
LIST_TAGS = {"ul", "ol"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK_TAGS = {
    "p",
    "div",
    "main",
    "section",
    "article",
    "table",
    "nav",
    "dialog",
    "blockquote",
    "header",
    "footer",
    "ul",
    "ol",
}


def safe_link(value: str, base: str = "") -> str:
    """Strip credentials/query/fragment; extracted query values may be tokens."""
    if not value:
        return ""
    try:
        parts = urlsplit(urljoin(base, value))
        if parts.scheme not in {"http", "https"}:
            return "[unsupported destination]"
        host = parts.hostname or ""
        if ":" in host:
            host = "[" + host + "]"
        if parts.port:
            host += ":" + str(parts.port)
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    except ValueError:
        return "[invalid destination]"


def _validate_tree(soup: BeautifulSoup, limits: Limits) -> int:
    """Bound recursive rendering with an iterative node/depth check first."""
    stack: list[tuple[Any, int]] = [(soup, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > limits.html_nodes or depth > limits.html_depth:
            raise AeroError(
                "HTML_LIMIT_EXCEEDED", "HTML node or nesting limit exceeded"
            )
        if isinstance(node, Tag):
            stack.extend((child, depth + 1) for child in node.children)
    return count


def _document_title(soup: BeautifulSoup, html: str) -> str:
    if soup.title:
        return soup.title.get_text(" ", strip=True)
    return "Untitled Page" if html else ""


def _sanitize(soup: BeautifulSoup, unwanted_tags: set[str]) -> None:
    for node in soup.find_all(
        string=lambda s: isinstance(
            s, (Comment, Declaration, Doctype, ProcessingInstruction)
        )
    ):
        node.extract()
    for node in soup.find_all(unwanted_tags):
        node.decompose()
    for node in soup.select(
        '[hidden], [inert], [aria-hidden="true"], input[type="hidden"]'
    ):
        if node.parent:
            node.decompose()
    # Never expose form values, including text/textarea fields and selected tokens.
    for node in soup.find_all(["input", "textarea", "select"]):
        if node.name == "textarea":
            node.clear()
        node.attrs.pop("value", None)


def _interactive_candidate(node: Tag) -> bool:
    if node.name not in INTERACTIVE and str(node.get("role", "")) not in ROLES:
        return False
    return node.name != "a" or node.has_attr("href")


def _referenced_label(node: Tag, soup: BeautifulSoup) -> str:
    if not node.get("aria-labelledby"):
        return ""
    return " ".join(
        found.get_text(" ", strip=True)
        for identifier in str(node["aria-labelledby"]).split()
        if (found := soup.find(id=identifier)) is not None
    )


def _action_label(node: Tag, soup: BeautifulSoup) -> str:
    label = str(node.get("aria-label") or "")
    if not label:
        label = _referenced_label(node, soup)
    if not label and node.get("id"):
        labels = soup.find_all("label", attrs={"for": node["id"]})
        label = " ".join(_label_text(item) for item in labels)
    if not label and (wrapped := node.find_parent("label")) is not None:
        label = _label_text(wrapped)
    text = node.get_text(" ", strip=True)
    if not text:
        text = " ".join(str(image.get("alt", "")) for image in node.find_all("img"))
    if text.endswith(("...", "…")) and node.get("title"):
        text = str(node["title"])
    return label or text or str(node.get("placeholder") or node.get("title") or "")


def _label_text(label: Tag) -> str:
    """A control's option values and descendant controls are not its label."""
    parts = []
    for text in label.find_all(string=True):
        if not any(
            parent.name in {"input", "textarea", "select"} for parent in text.parents
        ):
            parts.append(str(text).strip())
    return " ".join(part for part in parts if part)


def _action(
    node: Tag, soup: BeautifulSoup, base_url: str, index: int
) -> dict[str, Any]:
    label = _action_label(node, soup)
    return {
        "id": str(index),
        "tag": node.name,
        "element_type": node.name,
        "label": label,
        "accessible_name": label,
        "role": str(node.get("role", "")),
        "input_type": str(node.get("type", "")),
        "value": None,
        "disabled": node.has_attr("disabled") or node.get("aria-disabled") == "true",
        "visible": None,
        "executable": False,
        "generation": None,
        "href": safe_link(str(node.get("href", "")), base_url),
        "name": str(node.get("name", "")),
        "attributes": {
            "required": node.has_attr("required"),
            "readonly": node.has_attr("readonly"),
        },
    }


def _actions(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    candidates = (node for node in soup.find_all(True) if _interactive_candidate(node))
    return [
        _action(node, soup, base_url, index) for index, node in enumerate(candidates, 1)
    ]


def _table_text(node: Tag, table: Tag) -> str:
    return " ".join(
        str(text).strip()
        for text in node.find_all(string=True)
        if text.find_parent("table") is table and str(text).strip()
    )


def _table_cell(
    cell: Tag, table: Tag, indexes: dict[int, int], own_headers: dict[str, str]
) -> dict[str, Any]:
    headers = cell.get("headers", [])
    if isinstance(headers, str):
        headers = headers.split()
    return {
        "text": _table_text(cell, table),
        "header": cell.name == "th",
        "id": cell.get("id"),
        "scope": cell.get("scope"),
        "headers": headers,
        "resolved_headers": [
            {"id": identifier, "text": own_headers[identifier]}
            for identifier in headers
            if identifier in own_headers
        ],
        "nested_tables": [
            indexes[id(child)]
            for child in cell.find_all("table")
            if child.find_parent("table") is table
        ],
        "rowspan": cell.get("rowspan", "1"),
        "colspan": cell.get("colspan", "1"),
    }


def _table(table: Tag, indexes: dict[int, int]) -> dict[str, Any]:
    own_headers = {
        str(header["id"]): _table_text(header, table)
        for header in table.find_all("th", id=True)
        if header.find_parent("table") is table
    }
    rows = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is table:
            rows.append(
                [
                    _table_cell(cell, table, indexes, own_headers)
                    for cell in row.find_all(["th", "td"], recursive=False)
                ]
            )
    parent = table.find_parent("table")
    parent_cell = table.find_parent(["td", "th"])
    location = None
    if parent is not None and parent_cell is not None:
        parent_rows = [
            row for row in parent.find_all("tr") if row.find_parent("table") is parent
        ]
        for row_index, row in enumerate(parent_rows):
            for column, cell in enumerate(row.find_all(["td", "th"], recursive=False)):
                if cell is parent_cell:
                    location = {"row": row_index, "column": column}
    caption = table.find("caption", recursive=False)
    return {
        "caption": _table_text(caption, table) if isinstance(caption, Tag) else "",
        "rows": rows,
        "parent_table": indexes[id(parent)] if parent is not None else None,
        "parent_cell": location,
    }


def _render_embedded(node: Tag, base_url: str) -> str:
    label = str(node.get("title") or node.get("aria-label") or node.name)
    destination = safe_link(str(node.get("src") or node.get("data") or ""), base_url)
    return "\n[Embedded content inaccessible: " + label + " " + destination + "]\n"


def _render_image(node: Tag, base_url: str) -> str:
    return (
        "!["
        + str(node.get("alt", ""))
        + "]("
        + safe_link(str(node.get("src", "")), base_url)
        + ")"
    )


def _render_input(node: Tag) -> str:
    label = str(node.get("aria-label") or node.get("placeholder") or "")
    checked = " checked" if node.has_attr("checked") else ""
    return "[input " + str(node.get("type", "text")) + " " + label + checked + "]"


def _render_link(node: Tag, text: str, base_url: str) -> str:
    if text.strip().endswith(("...", "…")) and node.get("title"):
        text = str(node["title"])
    return (
        "[" + text.strip() + "](" + safe_link(str(node.get("href", "")), base_url) + ")"
    )


def _format_container(node: Tag, text: str, depth: int, base_url: str) -> str:
    tag = node.name
    if tag == "a":
        return _render_link(node, text, base_url)
    if tag in HEADING_TAGS:
        return "\n\n" + "#" * int(tag[1]) + " " + text.strip() + "\n\n"
    if tag == "li":
        return "\n" + "  " * max(0, depth - 1) + "- " + text.strip() + "\n"
    if tag in {"td", "th"}:
        return " " + text.strip().replace("|", "\\|") + " |"
    if tag == "tr":
        return "\n|" + text + "\n"
    if tag == "br":
        return "\n"
    if tag == "pre":
        return "\n```\n" + text + "\n```\n"
    if tag in BLOCK_TAGS:
        return "\n" + text.strip() + "\n"
    return text


def _render(node: Any, base_url: str, depth: int = 0) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name in EMBEDDED_TAGS:
        return _render_embedded(node, base_url)
    if node.name == "img":
        return _render_image(node, base_url)
    if node.name == "input":
        return _render_input(node)
    if node.name in LIST_TAGS:
        return _render_list(node, base_url, depth)
    child_depth = depth + (1 if node.name in LIST_TAGS else 0)
    text = "".join(_render(child, base_url, child_depth) for child in node.children)
    return _format_container(node, text, depth, base_url)


def _list_number(value: Any, default: int) -> int:
    # HTML list ordinals are signed 32-bit integers; malformed values use defaults.
    try:
        number = int(str(value))
        return number if -(2**31) <= number < 2**31 else default
    except (ValueError, TypeError):
        return default


def _render_list(node: Tag, base_url: str, depth: int) -> str:
    items = node.find_all("li", recursive=False)
    reverse = node.name == "ol" and node.has_attr("reversed")
    ordinal = _list_number(node.get("start"), len(items) if reverse else 1)
    rendered = []
    for child in node.children:
        if isinstance(child, Tag) and child.name == "li":
            ordinal = _list_number(child.get("value"), ordinal)
            marker = str(ordinal) + ". " if node.name == "ol" else "- "
            content = "".join(
                _render(part, base_url, depth + 1) for part in child.children
            ).strip()
            rendered.append("  " * depth + marker + content)
            ordinal += -1 if reverse else 1
        else:
            content = _render(child, base_url, depth + 1).strip("\n")
            if content.strip():
                rendered.append(content)
    return "\n" + "\n".join(rendered) + "\n"


class SemanticPruner:
    UNWANTED_TAGS: ClassVar[set[str]] = {
        "script",
        "style",
        "noscript",
        "svg",
        "path",
        "meta",
        "link",
        "template",
    }

    def __init__(self, *, limits: Limits | None = None, tokenizer: str = "cl100k_base"):
        self.limits, self.tokenizer = limits or Limits(), tokenizer

    def prune(self, html: str, base_url: str = "") -> dict[str, Any]:
        if len(html.encode("utf-8")) > self.limits.response_bytes:
            raise AeroError("HTML_TOO_LARGE", "HTML exceeds parser byte limit")
        soup = BeautifulSoup(html, "html.parser")
        count = _validate_tree(soup, self.limits)
        title = _document_title(soup, html)
        _sanitize(soup, self.UNWANTED_TAGS)
        embedded = soup.find_all(list(EMBEDDED_TAGS))
        tables = soup.find_all("table")
        indexes = {id(table): index for index, table in enumerate(tables)}
        markdown = re.sub(
            r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", _render(soup, base_url)
        ).strip()
        result = {
            "title": title,
            "markdown": markdown,
            "actions": _actions(soup, base_url),
            "tables": [_table(table, indexes) for table in tables],
            "original_chars": len(html),
            "pruned_chars": len(markdown),
            "character_reduction_pct": round((1 - len(markdown) / len(html)) * 100, 2)
            if html
            else 0.0,
            "quality": {
                "node_count": count,
                "empty_content": not bool(markdown),
                "embedded_content_inaccessible": len(embedded),
                "visibility_verified": False,
                "missing_content_indicators": ["embedded_content"] if embedded else [],
            },
        }
        result.update(measure(html, markdown, self.tokenizer))
        result.update(measure_output(result))
        return result
