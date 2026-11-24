"""Bidirectional Markdown <-> Notion block converter."""

from __future__ import annotations

import re
from typing import Any

MAX_RICH_TEXT_LEN = 1900

_INLINE_PATTERN = re.compile(
    r"(\*\*[^*]+\*\*|`[^`]+`|~~[^~]+~~|\[[^\]]+\]\([^\)]+\)|\*[^*]+\*)"
)


def rich_text_to_markdown(rich_text: list[dict[str, Any]]) -> str:
    """Convert Notion rich_text array to inline Markdown."""
    parts: list[str] = []
    for seg in rich_text:
        text = seg.get("plain_text", "")
        if not text:
            continue
        ann = seg.get("annotations", {})
        href = seg.get("href") or seg.get("text", {}).get("link", {})
        if isinstance(href, dict):
            href = href.get("url")

        if ann.get("code"):
            text = f"`{text}`"
        if ann.get("bold"):
            text = f"**{text}**"
        if ann.get("italic"):
            text = f"*{text}*"
        if ann.get("strikethrough"):
            text = f"~~{text}~~"
        if href:
            text = f"[{text}]({href})"
        parts.append(text)
    return "".join(parts)


def markdown_to_rich_text(text: str) -> list[dict[str, Any]]:
    """Parse basic inline Markdown (**bold**, *italic*, `code`, ~~strike~~, [link](url))."""
    if not text:
        return []

    segments: list[dict[str, Any]] = []
    pos = 0
    for match in _INLINE_PATTERN.finditer(text):
        if match.start() > pos:
            segments.extend(_chunk_plain_text(text[pos : match.start()]))
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            segments.append(_make_rt(token[2:-2], bold=True))
        elif token.startswith("`") and token.endswith("`"):
            segments.append(_make_rt(token[1:-1], code=True))
        elif token.startswith("~~") and token.endswith("~~"):
            segments.append(_make_rt(token[2:-2], strikethrough=True))
        elif token.startswith("*") and token.endswith("*"):
            segments.append(_make_rt(token[1:-1], italic=True))
        elif token.startswith("[") and "](" in token and token.endswith(")"):
            label, url = token[1:-1].split("](", 1)
            segments.append(_make_rt(label, url=url))
        else:
            segments.extend(_chunk_plain_text(token))
        pos = match.end()

    if pos < len(text):
        segments.extend(_chunk_plain_text(text[pos:]))
    return segments


def _chunk_plain_text(text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for i in range(0, len(text), MAX_RICH_TEXT_LEN):
        chunks.append(_make_rt(text[i : i + MAX_RICH_TEXT_LEN]))
    return chunks


def _make_rt(
    content: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    strikethrough: bool = False,
    url: str | None = None,
) -> dict[str, Any]:
    text_obj: dict[str, Any] = {"content": content[:MAX_RICH_TEXT_LEN]}
    if url:
        text_obj["link"] = {"url": url}
    item: dict[str, Any] = {"type": "text", "text": text_obj}
    annotations: dict[str, bool] = {}
    if bold:
        annotations["bold"] = True
    if italic:
        annotations["italic"] = True
    if code:
        annotations["code"] = True
    if strikethrough:
        annotations["strikethrough"] = True
    if annotations:
        item["annotations"] = annotations
    return item


def blocks_to_markdown(
    blocks: list[dict[str, Any]],
    indent: int = 0,
    compact: bool = False,
) -> str:
    """Render Notion block tree (including nested `_children`) into Markdown."""
    lines: list[str] = []
    prefix = "  " * indent

    for block in blocks:
        btype = block.get("type", "")
        data = block.get(btype, {})
        rt = data.get("rich_text", [])
        text = rich_text_to_markdown(rt) if rt else ""

        if btype == "heading_1":
            lines.append(f"{prefix}# {text}")
        elif btype == "heading_2":
            lines.append(f"{prefix}## {text}")
        elif btype == "heading_3":
            lines.append(f"{prefix}### {text}")
        elif btype == "paragraph":
            if text or not compact:
                lines.append(f"{prefix}{text}")
        elif btype == "bulleted_list_item":
            lines.append(f"{prefix}- {text}")
        elif btype == "numbered_list_item":
            lines.append(f"{prefix}1. {text}")
        elif btype == "to_do":
            mark = "x" if data.get("checked") else " "
            lines.append(f"{prefix}- [{mark}] {text}")
        elif btype == "quote":
            lines.append(f"{prefix}> {text}")
        elif btype == "callout":
            icon = data.get("icon", {})
            emoji = icon.get("emoji", "💡") if isinstance(icon, dict) else "💡"
            lines.append(f"{prefix}> {emoji} {text}")
        elif btype == "code":
            lang = data.get("language", "")
            raw_code = "".join(x.get("plain_text", "") for x in rt)
            lines.append(f"{prefix}```{lang}\n{raw_code}\n{prefix}```")
        elif btype == "divider":
            if not compact:
                lines.append(f"{prefix}---")
        elif btype == "toggle":
            lines.append(f"{prefix}- **{text}**")
        elif btype == "table":
            rows = block.get("_children", [])
            table_md = _table_rows_to_markdown(rows, prefix)
            if table_md:
                lines.append(table_md)
            continue
        elif btype == "child_page":
            title = data.get("title", "")
            if compact:
                lines.append(f"{prefix}[PAGE] {title} ({block.get('id')})")
            else:
                lines.append(f"{prefix}📄 [Page] {title} (ID: {block.get('id')})")
        elif btype == "child_database":
            title = data.get("title", "")
            if compact:
                lines.append(f"{prefix}[DB] {title} ({block.get('id')})")
            else:
                lines.append(f"{prefix}🗂️ [Database] {title} (ID: {block.get('id')})")
        elif text:
            lines.append(f"{prefix}{text}")

        children = block.get("_children")
        if children and btype != "table":
            nested = blocks_to_markdown(children, indent=indent + 1, compact=compact)
            if nested:
                lines.append(nested)

    return "\n".join(line for line in lines if line is not None)


def _table_rows_to_markdown(rows: list[dict[str, Any]], prefix: str = "") -> str:
    rendered: list[str] = []
    for idx, row in enumerate(rows):
        if row.get("type") != "table_row":
            continue
        cells = row.get("table_row", {}).get("cells", [])
        cell_texts = [rich_text_to_markdown(c).replace("|", "\\|") for c in cells]
        rendered.append(f"{prefix}| " + " | ".join(cell_texts) + " |")
        if idx == 0:
            rendered.append(
                f"{prefix}| " + " | ".join("---" for _ in cell_texts) + " |"
            )
    return "\n".join(rendered)


def markdown_to_blocks(markdown_text: str) -> list[dict[str, Any]]:
    """Convert Markdown text into a list of Notion API block payloads."""
    blocks: list[dict[str, Any]] = []
    lines = markdown_text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "plain text"
            code_lines: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume closing fence
            code_text = "\n".join(code_lines)
            blocks.append(
                {
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": _chunk_plain_text(code_text),
                        "language": _normalize_code_lang(lang),
                    },
                }
            )
            continue

        # Markdown table
        if stripped.startswith("|") and stripped.endswith("|") and i + 1 < n:
            next_s = lines[i + 1].strip()
            if next_s.startswith("|") and set(next_s.replace("|", "").replace(" ", "")) <= {"-", ":"}:
                table_lines = [stripped]
                i += 2  # skip header + separator
                while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                blocks.append(_build_table_block(table_lines))
                continue

        if stripped.startswith("### "):
            blocks.append(_text_block("heading_3", stripped[4:]))
        elif stripped.startswith("## "):
            blocks.append(_text_block("heading_2", stripped[3:]))
        elif stripped.startswith("# "):
            blocks.append(_text_block("heading_1", stripped[2:]))
        elif re.match(r"^- \[[ xX]\] ", stripped):
            checked = stripped[3].lower() == "x"
            blocks.append(
                {
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": markdown_to_rich_text(stripped[6:]),
                        "checked": checked,
                    },
                }
            )
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(_text_block("bulleted_list_item", stripped[2:]))
        elif re.match(r"^\d+\.\s+", stripped):
            item_text = re.sub(r"^\d+\.\s+", "", stripped)
            blocks.append(_text_block("numbered_list_item", item_text))
        elif stripped.startswith("> "):
            blocks.append(_text_block("quote", stripped[2:]))
        elif stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        else:
            blocks.append(_text_block("paragraph", stripped))

        i += 1

    return blocks


def _text_block(block_type: str, text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": markdown_to_rich_text(text)},
    }


def _build_table_block(table_lines: list[str]) -> dict[str, Any]:
    parsed_rows = [
        [cell.strip() for cell in line.strip("|").split("|")] for line in table_lines
    ]
    width = max(len(r) for r in parsed_rows)
    children = []
    for row in parsed_rows:
        padded = row + [""] * (width - len(row))
        children.append(
            {
                "object": "block",
                "type": "table_row",
                "table_row": {
                    "cells": [markdown_to_rich_text(cell) for cell in padded]
                },
            }
        )
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": children,
        },
    }


_VALID_LANGS = {
    "bash", "c", "c++", "css", "diff", "docker", "go", "html", "java",
    "javascript", "json", "kotlin", "latex", "markdown", "plain text",
    "python", "rust", "shell", "sql", "swift", "toml", "typescript", "yaml",
}


def _normalize_code_lang(lang: str) -> str:
    low = lang.lower().strip()
    aliases = {"py": "python", "js": "javascript", "ts": "typescript", "sh": "bash", "yml": "yaml", "md": "markdown"}
    low = aliases.get(low, low)
    return low if low in _VALID_LANGS else "plain text"
