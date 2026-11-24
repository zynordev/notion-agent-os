# AGENTS.md — notion-agent-os

## Overview
`notion-agent-os` is a zero-dependency Python 3.10+ CLI and automation toolkit for building and operating an AI-agent-first Notion Life OS.

## Architecture
- `src/notion_agent_os/config.py`: Token and workspace manifest management.
- `src/notion_agent_os/client.py`: Stdlib Notion REST API client (pagination, 429 retry, recursive block fetch).
- `src/notion_agent_os/markdown.py`: Bidirectional Markdown <-> Notion block engine.
- `src/notion_agent_os/schema.py`: Schema-as-Code Life OS bootstrapper (`init`).
- `src/notion_agent_os/ingest.py`: External data ingestion (`.ics` calendar events, `git` commit summaries).
- `src/notion_agent_os/brief.py`: Daily briefing generator (upcoming events + open tasks, `--compact` mode).
- `src/notion_agent_os/export.py`: Recursive Notion-to-Markdown exporter (Obsidian-compatible).
- `src/notion_agent_os/cli.py`: `notion-os` CLI entrypoint.

## Rules for Contributors & AI Agents
1. **Zero runtime dependencies:** Keep core runtime strictly Python standard library (`urllib`, `json`, `argparse`, `pathlib`, etc.).
2. **Privacy & Security:** NEVER commit real Notion tokens (`ntn_...`), personal page/workspace IDs, or personal data. All templates and tests must use anonymized sample data.
3. **Verification:** Run `python3 -m unittest discover -s tests -v` before committing.
