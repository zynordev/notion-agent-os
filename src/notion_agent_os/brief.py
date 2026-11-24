"""Daily briefing generator: upcoming calendar events + open to-do tasks."""

from __future__ import annotations

import datetime as dt
from typing import Any

from .client import NotionClient, extract_title
from .markdown import rich_text_to_markdown


def extract_open_todos(blocks: list[dict[str, Any]]) -> list[str]:
    """Recursively collect unchecked `to_do` items from a Notion block tree."""
    todos: list[str] = []
    for block in blocks:
        if block.get("type") == "to_do":
            data = block.get("to_do", {})
            if not data.get("checked"):
                text = rich_text_to_markdown(data.get("rich_text", [])).strip()
                if text:
                    todos.append(text)
        children = block.get("_children")
        if children:
            todos.extend(extract_open_todos(children))
    return todos


def extract_event_row(row: dict[str, Any]) -> dict[str, str]:
    """Extract normalized event fields from a Notion Calendar DB row."""
    title = extract_title(row)
    props = row.get("properties", {})
    date_start = ""
    date_end = ""
    location = ""
    category = ""

    for prop in props.values():
        ptype = prop.get("type")
        if ptype == "date" and prop.get("date"):
            date_start = prop["date"].get("start") or ""
            date_end = prop["date"].get("end") or ""
        elif ptype == "select" and prop.get("select"):
            if not category:
                category = prop["select"].get("name", "")
        elif ptype == "rich_text" and prop.get("rich_text"):
            if not location:
                location = "".join(x.get("plain_text", "") for x in prop["rich_text"])

    return {
        "title": title,
        "start": date_start,
        "end": date_end,
        "category": category,
        "location": location,
    }


def generate_briefing(
    client: NotionClient,
    *,
    calendar_db_id: str | None = None,
    page_ids: list[str] | None = None,
    days: int = 7,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """Fetch upcoming events and open tasks across configured Notion targets."""
    ref_day = today or dt.date.today()
    end_day = ref_day + dt.timedelta(days=days)

    events: list[dict[str, str]] = []
    if calendar_db_id:
        rows = client.query_database(
            calendar_db_id,
            filter_obj={
                "and": [
                    {"property": "Date", "date": {"on_or_after": ref_day.isoformat()}},
                    {"property": "Date", "date": {"on_or_before": end_day.isoformat()}},
                ]
            },
            sorts=[{"property": "Date", "direction": "ascending"}],
            limit=50,
        )
        events = [extract_event_row(r) for r in rows]

    tasks_by_page: dict[str, list[str]] = {}
    for pid in page_ids or []:
        page = client.get_page(pid)
        title = extract_title(page)
        blocks = client.get_block_children(pid, recursive=True, max_depth=2)
        open_todos = extract_open_todos(blocks)
        if open_todos:
            tasks_by_page[title] = open_todos

    return {
        "date": ref_day.isoformat(),
        "window_days": days,
        "events": events,
        "tasks": tasks_by_page,
    }


def format_briefing(data: dict[str, Any], compact: bool = False) -> str:
    """Format briefing dictionary into human-readable or token-efficient output."""
    lines: list[str] = []
    if compact:
        lines.append(f"BRIEF {data['date']} (+{data['window_days']}d)")
        if data["events"]:
            lines.append("EVENTS:")
            for ev in data["events"]:
                loc = f" @ {ev['location']}" if ev.get("location") else ""
                lines.append(f"- {ev['start']} | {ev['title']}{loc}")
        else:
            lines.append("EVENTS: none")
        if data["tasks"]:
            lines.append("TASKS:")
            for page_title, todos in data["tasks"].items():
                for t in todos:
                    lines.append(f"- [{page_title}] {t}")
        else:
            lines.append("TASKS: none")
        return "\n".join(lines)

    lines.append(f"# Daily Briefing ({data['date']})")
    lines.append("")
    lines.append(f"## Upcoming Events (Next {data['window_days']} Days)")
    if data["events"]:
        for ev in data["events"]:
            span = f"{ev['start']} -> {ev['end']}" if ev.get("end") else ev["start"]
            meta = " | ".join(x for x in (ev.get("category"), ev.get("location")) if x)
            suffix = f" ({meta})" if meta else ""
            lines.append(f"- **{span}**: {ev['title']}{suffix}")
    else:
        lines.append("- No upcoming events found.")

    lines.append("")
    lines.append("## Open Tasks")
    if data["tasks"]:
        for page_title, todos in data["tasks"].items():
            lines.append(f"### {page_title}")
            for t in todos:
                lines.append(f"- [ ] {t}")
    else:
        lines.append("- No open tasks found.")

    return "\n".join(lines)
