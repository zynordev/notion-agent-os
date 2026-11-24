---
name: notion-agent-os
description: Read, search, update, export, and automate a Notion Life OS workspace using the zero-dependency `notion-os` CLI. Use when managing tasks, calendar events, `.ics` imports, git activity logs, or daily briefings in Notion.
---

# notion-agent-os Skill

## Prerequisites
- `notion-os` installed on PATH (`pip install -e .`).
- Token configured via `NOTION_TOKEN` environment variable or `notion-os auth`.

## Token-Efficient Agent Workflow

1. **Discover pages & IDs:**
   ```bash
   notion-os search "<keyword>" --compact
   ```
2. **Get a daily briefing (upcoming events + open tasks):**
   ```bash
   notion-os brief --days 7 --compact
   ```
3. **Read a page with nested blocks:**
   ```bash
   notion-os read <page_id> --recursive --compact
   ```
4. **Append Markdown or tasks:**
   ```bash
   notion-os append <page_id> "## Update\n- [ ] Verify release notes"
   ```
5. **Ingest external sources:**
   ```bash
   notion-os ingest ics ./event.ics --category Travel
   notion-os ingest git --repo . --since "1 day ago" --page-id <notes_page_id>
   ```
6. **Backup / Obsidian sync:**
   ```bash
   notion-os export <hub_page_id> --out ./notion-backup --depth 3
   ```
