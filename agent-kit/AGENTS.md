# AGENTS.md — Multi-Agent Notion Memory Protocol

Drop this snippet into your global `AGENTS.md` / `CLAUDE.md` / `RULES.md` so **Claude Code**, **Codex CLI**, and **Antigravity** share a single Notion Life OS memory layer.

## Notion Memory Rules

1. **Query Notion First:** Before asking the user about ongoing projects, deadlines, tasks, or contacts, search Notion using token-efficient output:
   ```bash
   notion-os search "<query>" --compact
   notion-os read <page_id> --recursive --compact
   ```
2. **Daily Context:** When the user asks "what's on my plate today?" or "what are my upcoming deadlines?", run:
   ```bash
   notion-os brief --compact
   ```
3. **Standard Two-Layer Updates:** Every entity page has two subpages:
   - `Info` — static metadata (status, owner, links).
   - `Notes` — running logs, decisions, and `- [ ]` action items.
   Append new tasks or progress notes directly to `Notes`:
   ```bash
   notion-os append <notes_page_id> "- [ ] Follow up on benchmark results"
   ```
4. **Automated Ingestion:**
   - Calendar invites / flight `.ics` files: `notion-os ingest ics <file.ics>`
   - Daily coding progress: `notion-os ingest git --repo . --page-id <notes_page_id>`
5. **Security:** Never hardcode or print `NOTION_TOKEN` in prompts, logs, or commits.
