"""Recursive Notion-to-Markdown exporter (Obsidian-compatible)."""

from __future__ import annotations

import re
from pathlib import Path

from .client import NotionClient, extract_title
from .markdown import blocks_to_markdown


def _slugify(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] or "Untitled"


def export_page_tree(
    client: NotionClient,
    page_id: str,
    out_dir: str | Path,
    max_depth: int = 3,
    _depth: int = 0,
) -> list[Path]:
    """Recursively export a Notion page and its child pages into Markdown files."""
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    page = client.get_page(page_id)
    title = extract_title(page)
    blocks = client.get_block_children(page_id, recursive=True, max_depth=3)
    md_body = blocks_to_markdown(blocks)

    frontmatter = (
        "---\n"
        f'notion_id: "{page.get("id", page_id)}"\n'
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f'url: "{page.get("url", "")}"\n'
        "---\n\n"
        f"# {title}\n\n"
    )

    filename = f"{_slugify(title)}.md"
    file_path = target_dir / filename
    file_path.write_text(frontmatter + md_body + "\n", encoding="utf-8")
    written = [file_path]

    if _depth < max_depth:
        child_pages = [b for b in blocks if b.get("type") == "child_page"]
        if child_pages:
            sub_dir = target_dir / _slugify(title)
            for child in child_pages:
                written.extend(
                    export_page_tree(
                        client,
                        child["id"],
                        sub_dir,
                        max_depth=max_depth,
                        _depth=_depth + 1,
                    )
                )

    return written
