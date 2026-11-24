"""External data ingestion modules: RFC 5545 `.ics` calendar events and `git` logs."""

from __future__ import annotations

import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import NotionClient
from .markdown import markdown_to_blocks


@dataclass
class CalendarEvent:
    summary: str
    start: str
    end: str | None = None
    location: str = ""
    description: str = ""
    category: str = "Event"


def _unfold_ics_lines(raw_text: str) -> list[str]:
    """Unfold RFC 5545 folded lines (CRLF/LF followed by space or tab)."""
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _unescape_ics_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_ics_datetime(raw_value: str) -> str:
    """Convert ICS DTSTART/DTEND (YYYYMMDD or YYYYMMDDTHHMMSS[Z]) into ISO 8601."""
    val = raw_value.strip()
    if re.fullmatch(r"\d{8}", val):
        return f"{val[0:4]}-{val[4:6]}-{val[6:8]}"
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)", val)
    if m:
        y, mo, d, h, mi, s, z = m.groups()
        suffix = "Z" if z else ""
        return f"{y}-{mo}-{d}T{h}:{mi}:{s}{suffix}"
    return val


def parse_ics(ics_text: str, default_category: str = "Event") -> list[CalendarEvent]:
    """Parse VEVENT blocks from an `.ics` string."""
    events: list[CalendarEvent] = []
    in_event = False
    current: dict[str, str] = {}

    for line in _unfold_ics_lines(ics_text):
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            in_event = True
            current = {}
            continue
        if stripped == "END:VEVENT":
            if in_event and current.get("SUMMARY") and current.get("DTSTART"):
                events.append(
                    CalendarEvent(
                        summary=_unescape_ics_text(current["SUMMARY"]),
                        start=_parse_ics_datetime(current["DTSTART"]),
                        end=_parse_ics_datetime(current["DTEND"])
                        if current.get("DTEND")
                        else None,
                        location=_unescape_ics_text(current.get("LOCATION", "")),
                        description=_unescape_ics_text(current.get("DESCRIPTION", "")),
                        category=default_category,
                    )
                )
            in_event = False
            current = {}
            continue

        if in_event and ":" in line:
            key_part, val = line.split(":", 1)
            prop_name = key_part.split(";", 1)[0].upper().strip()
            current[prop_name] = val

    return events


def parse_ics_file(path: str | Path, default_category: str = "Event") -> list[CalendarEvent]:
    return parse_ics(Path(path).read_text(encoding="utf-8"), default_category=default_category)


def ingest_ics_to_notion(
    client: NotionClient,
    db_id: str,
    ics_path: str | Path,
    category: str = "Event",
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Parse an `.ics` file and insert its events into a Notion Calendar DB."""
    events = parse_ics_file(ics_path, default_category=category)
    created: list[dict[str, Any]] = []

    for ev in events:
        date_val: dict[str, Any] = {"start": ev.start}
        if ev.end and ev.end != ev.start:
            date_val["end"] = ev.end

        props: dict[str, Any] = {
            "Name": {"title": [{"type": "text", "text": {"content": ev.summary}}]},
            "Date": {"date": date_val},
            "Category": {"select": {"name": ev.category}},
        }
        if ev.location:
            props["Location"] = {
                "rich_text": [{"type": "text", "text": {"content": ev.location[:1900]}}]
            }

        children = markdown_to_blocks(ev.description) if ev.description else None

        if dry_run:
            created.append(
                {
                    "dry_run": True,
                    "summary": ev.summary,
                    "start": ev.start,
                    "end": ev.end,
                    "location": ev.location,
                    "category": ev.category,
                }
            )
        else:
            page = client.create_page(
                parent_id=db_id,
                parent_type="database",
                title=ev.summary,
                properties=props,
                children=children,
            )
            created.append({"id": page["id"], "summary": ev.summary, "url": page.get("url", "")})

    return created


def collect_git_commits(
    repo_path: str | Path = ".",
    since: str = "1 day ago",
    max_count: int = 30,
) -> list[dict[str, str]]:
    """Collect recent git commits from a local repository."""
    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        f"--since={since}",
        f"-n{max_count}",
        "--pretty=format:%h|%ad|%an|%s",
        "--date=short",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "Failed to read git log.")
    commits: list[dict[str, str]] = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append(
                {
                    "hash": parts[0],
                    "date": parts[1],
                    "author": parts[2],
                    "subject": parts[3],
                }
            )
    return commits


def format_git_digest_markdown(
    repo_name: str,
    commits: list[dict[str, str]],
    date_label: str | None = None,
) -> str:
    """Format git commits into a clean Notion-ready Markdown digest."""
    label = date_label or dt.date.today().isoformat()
    lines = [f"### Git Activity — {repo_name} ({label})"]
    if not commits:
        lines.append("- No commits found in the requested window.")
        return "\n".join(lines)
    for c in commits:
        lines.append(f"- `{c['hash']}` {c['subject']} ({c['date']})")
    return "\n".join(lines)


def ingest_git_to_notion(
    client: NotionClient,
    page_id: str,
    repo_path: str | Path = ".",
    since: str = "1 day ago",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Append a git commit digest to a Notion page."""
    repo_dir = Path(repo_path).resolve()
    commits = collect_git_commits(repo_dir, since=since)
    md = format_git_digest_markdown(repo_dir.name, commits)
    if dry_run:
        return {"dry_run": True, "commit_count": len(commits), "markdown": md}
    blocks = markdown_to_blocks(md)
    created = client.append_blocks(page_id, blocks)
    return {
        "commit_count": len(commits),
        "blocks_added": len(created),
        "page_id": page_id,
    }
