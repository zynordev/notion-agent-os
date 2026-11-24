"""Schema-as-Code Life OS bootstrapper (`notion-os init`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .client import NotionClient
from .config import save_manifest
from .markdown import markdown_to_blocks


def load_schema(schema_path: str | Path) -> dict[str, Any]:
    """Load and validate a Life OS JSON schema template."""
    path = Path(schema_path)
    if not path.is_file():
        raise FileNotFoundError(f"Schema template not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_schema(data)
    return data


def validate_schema(schema: dict[str, Any]) -> None:
    """Validate required fields in a Life OS schema."""
    if not isinstance(schema, dict):
        raise ValueError("Schema root must be a JSON object.")
    if "hub" not in schema or not isinstance(schema["hub"], dict):
        raise ValueError("Schema must define a 'hub' object.")
    if not schema["hub"].get("title"):
        raise ValueError("Schema 'hub' must define a 'title'.")
    categories = schema.get("categories", [])
    if not isinstance(categories, list):
        raise ValueError("Schema 'categories' must be a list.")
    for idx, cat in enumerate(categories):
        if not isinstance(cat, dict) or not cat.get("title"):
            raise ValueError(f"Category #{idx} must have a 'title'.")


def build_plan(schema: dict[str, Any]) -> list[str]:
    """Generate a human-readable dry-run plan of resources to create."""
    hub = schema["hub"]
    lines = [f"[HUB] {hub.get('icon', '🧠')} {hub['title']}"]

    cal = schema.get("calendar_db")
    if cal:
        lines.append(f"  ├─ [DB] {cal.get('icon', '📅')} {cal.get('title', 'Calendar & Events')}")

    default_subpages = schema.get("default_entity_subpages", [
        {"title": "Info", "icon": "📋"},
        {"title": "Notes", "icon": "✍️"},
    ])

    for cat in schema.get("categories", []):
        lines.append(f"  ├─ [CATEGORY] {cat.get('icon', '📁')} {cat['title']}")
        for entity in cat.get("entities", []):
            lines.append(f"  │   └─ [ENTITY] {entity.get('icon', '📄')} {entity['title']}")
            subpages = entity.get("subpages", default_subpages)
            for sp in subpages:
                lines.append(f"  │       └─ [SUBPAGE] {sp.get('icon', '📝')} {sp['title']}")
    return lines


def bootstrap_workspace(
    client: NotionClient,
    parent_page_id: str,
    schema: dict[str, Any],
    manifest_path: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create the Life OS structure in Notion from a schema template."""
    validate_schema(schema)
    if dry_run:
        return {"dry_run": True, "plan": build_plan(schema)}

    hub_cfg = schema["hub"]
    hub_intro = hub_cfg.get("intro_markdown", "")
    hub_children = markdown_to_blocks(hub_intro) if hub_intro else None
    hub_page = client.create_page(
        parent_id=parent_page_id,
        title=hub_cfg["title"],
        icon_emoji=hub_cfg.get("icon"),
        children=hub_children,
    )
    hub_id = hub_page["id"]

    manifest: dict[str, Any] = {
        "schema_name": schema.get("name", "custom"),
        "hub_id": hub_id,
        "hub_url": hub_page.get("url", ""),
        "calendar_db_id": None,
        "categories": {},
    }

    # Optional Calendar Database
    cal_cfg = schema.get("calendar_db")
    if cal_cfg:
        cal_props = cal_cfg.get(
            "properties",
            {
                "Name": {"title": {}},
                "Date": {"date": {}},
                "Category": {
                    "select": {
                        "options": [
                            {"name": "Academic", "color": "blue"},
                            {"name": "Project", "color": "purple"},
                            {"name": "Event", "color": "green"},
                            {"name": "Travel", "color": "orange"},
                            {"name": "Personal", "color": "gray"},
                        ]
                    }
                },
                "Location": {"rich_text": {}},
                "Status": {
                    "select": {
                        "options": [
                            {"name": "Planned", "color": "yellow"},
                            {"name": "Confirmed", "color": "green"},
                            {"name": "Done", "color": "gray"},
                        ]
                    }
                },
            },
        )
        cal_db = client.create_database(
            parent_page_id=hub_id,
            title=cal_cfg.get("title", "Calendar & Events"),
            properties=cal_props,
            icon_emoji=cal_cfg.get("icon", "📅"),
        )
        manifest["calendar_db_id"] = cal_db["id"]

    default_subpages = schema.get(
        "default_entity_subpages",
        [
            {"title": "Info", "icon": "📋", "markdown": "## Overview\n- Owner:\n- Status: Active\n"},
            {"title": "Notes", "icon": "✍️", "markdown": "## Action Items\n- [ ] Initial setup\n"},
        ],
    )

    for cat in schema.get("categories", []):
        cat_intro = cat.get("intro_markdown", "")
        cat_page = client.create_page(
            parent_id=hub_id,
            title=cat["title"],
            icon_emoji=cat.get("icon"),
            children=markdown_to_blocks(cat_intro) if cat_intro else None,
        )
        cat_key = cat.get("key") or cat["title"]
        cat_record: dict[str, Any] = {
            "id": cat_page["id"],
            "title": cat["title"],
            "entities": {},
        }

        for entity in cat.get("entities", []):
            ent_page = client.create_page(
                parent_id=cat_page["id"],
                title=entity["title"],
                icon_emoji=entity.get("icon"),
                children=markdown_to_blocks(entity["intro_markdown"])
                if entity.get("intro_markdown")
                else None,
            )
            ent_record: dict[str, Any] = {
                "id": ent_page["id"],
                "title": entity["title"],
                "subpages": {},
            }
            for sp in entity.get("subpages", default_subpages):
                sp_page = client.create_page(
                    parent_id=ent_page["id"],
                    title=sp["title"],
                    icon_emoji=sp.get("icon"),
                    children=markdown_to_blocks(sp["markdown"])
                    if sp.get("markdown")
                    else None,
                )
                ent_record["subpages"][sp["title"]] = sp_page["id"]
            cat_record["entities"][entity["title"]] = ent_record

        manifest["categories"][cat_key] = cat_record

    saved_to = save_manifest(manifest, manifest_path)
    manifest["_manifest_path"] = str(saved_to)
    return manifest
