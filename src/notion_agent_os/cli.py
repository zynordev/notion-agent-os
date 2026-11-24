"""Command-line interface for notion-agent-os (`notion-os`)."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .brief import format_briefing, generate_briefing
from .client import NotionAPIError, NotionClient, extract_title
from .config import ConfigError, load_manifest, save_token
from .export import export_page_tree
from .ingest import ingest_git_to_notion, ingest_ics_to_notion
from .markdown import blocks_to_markdown, markdown_to_blocks
from .schema import bootstrap_workspace, load_schema


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_auth(args: argparse.Namespace) -> None:
    token = args.token
    if not token:
        token = getpass.getpass("Notion Internal Integration Token (ntn_...): ").strip()
    saved = save_token(token)
    print(f"Token saved securely to {saved} (mode 0600).")


def cmd_whoami(args: argparse.Namespace) -> None:
    client = NotionClient()
    res = client.whoami()
    if args.json:
        _print_json(res)
        return
    bot = res.get("bot", {})
    print(f"Integration : {res.get('name')} ({res.get('id')})")
    print(f"Workspace   : {bot.get('workspace_name')} ({bot.get('workspace_id')})")


def cmd_search(args: argparse.Namespace) -> None:
    client = NotionClient()
    results = client.search(query=args.query, obj_type=args.type, limit=args.limit)
    if args.json:
        _print_json(results)
        return
    if not results:
        print("No matching pages or databases found. Ensure the integration is connected to your page.")
        return
    for item in results:
        obj = item.get("object", "").upper()
        title = extract_title(item)
        if args.compact:
            print(f"[{obj}] {title} | {item.get('id')}")
        else:
            print(f"[{obj}] {title}\n  ID : {item.get('id')}\n  URL: {item.get('url', '')}")


def cmd_read(args: argparse.Namespace) -> None:
    client = NotionClient()
    page = client.get_page(args.page_id)
    blocks = client.get_block_children(
        args.page_id,
        recursive=args.recursive,
        max_depth=args.depth,
    )
    if args.json:
        _print_json({"page": page, "blocks": blocks})
        return
    title = extract_title(page)
    if args.compact:
        print(f"# {title} ({page.get('id')})")
    else:
        print(f"=== {title} ===")
        print(f"ID : {page.get('id')}")
        print(f"URL: {page.get('url', '')}\n")
    print(blocks_to_markdown(blocks, compact=args.compact))


def cmd_append(args: argparse.Namespace) -> None:
    client = NotionClient()
    blocks = markdown_to_blocks(args.text)
    created = client.append_blocks(args.page_id, blocks)
    print(f"Appended {len(created)} block(s).")


def cmd_push(args: argparse.Namespace) -> None:
    client = NotionClient()
    md_text = Path(args.file).read_text(encoding="utf-8")
    blocks = markdown_to_blocks(md_text)
    if args.dry_run:
        print(f"[DRY-RUN] Would push {len(blocks)} block(s) from {args.file} to {args.page_id}.")
        return
    created = client.append_blocks(args.page_id, blocks)
    print(f"Pushed {len(created)} block(s) from {args.file}.")


def cmd_create_page(args: argparse.Namespace) -> None:
    client = NotionClient()
    children = markdown_to_blocks(args.text) if args.text else None
    page = client.create_page(
        parent_id=args.parent_id,
        parent_type=args.parent_type,
        title=args.title,
        icon_emoji=args.icon,
        children=children,
    )
    if args.json:
        _print_json(page)
        return
    print(f"Created page: {extract_title(page)}")
    print(f"ID : {page.get('id')}")
    print(f"URL: {page.get('url', '')}")


def cmd_db_query(args: argparse.Namespace) -> None:
    client = NotionClient()
    filter_obj = json.loads(args.filter) if args.filter else None
    rows = client.query_database(args.db_id, filter_obj=filter_obj, limit=args.limit)
    if args.json:
        _print_json(rows)
        return
    for row in rows:
        print(f"- {extract_title(row)} ({row.get('id')})")


def cmd_raw(args: argparse.Namespace) -> None:
    client = NotionClient()
    payload = json.loads(args.data) if args.data else None
    res = client.request(args.method.upper(), args.endpoint, payload)
    _print_json(res)


def cmd_init(args: argparse.Namespace) -> None:
    schema = load_schema(args.template)
    client = NotionClient() if not args.dry_run else NotionClient(token="dry-run")
    result = bootstrap_workspace(
        client,
        parent_page_id=args.parent_id or "dry-run-parent",
        schema=schema,
        manifest_path=args.manifest,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("\n".join(result["plan"]))
        return
    if args.json:
        _print_json(result)
        return
    print(f"Life OS bootstrapped: {result['hub_url']}")
    print(f"Hub ID     : {result['hub_id']}")
    print(f"Calendar DB: {result.get('calendar_db_id') or 'none'}")
    print(f"Manifest   : {result.get('_manifest_path')}")


def cmd_brief(args: argparse.Namespace) -> None:
    manifest = load_manifest(args.manifest)
    cal_id = args.calendar_db or manifest.get("calendar_db_id")
    page_ids = list(args.page_id or [])
    if not page_ids and manifest.get("hub_id"):
        page_ids.append(manifest["hub_id"])

    client = NotionClient()
    data = generate_briefing(
        client,
        calendar_db_id=cal_id,
        page_ids=page_ids,
        days=args.days,
    )
    if args.json:
        _print_json(data)
        return
    print(format_briefing(data, compact=args.compact))


def cmd_export(args: argparse.Namespace) -> None:
    client = NotionClient()
    files = export_page_tree(
        client,
        page_id=args.page_id,
        out_dir=args.out,
        max_depth=args.depth,
    )
    print(f"Exported {len(files)} Markdown file(s) to {args.out}:")
    for f in files:
        print(f"  - {f}")


def cmd_ingest_ics(args: argparse.Namespace) -> None:
    manifest = load_manifest(args.manifest)
    db_id = args.calendar_db or manifest.get("calendar_db_id")
    if not db_id and not args.dry_run:
        raise ConfigError("Provide --calendar-db or initialize a workspace manifest first.")
    client = NotionClient() if not args.dry_run else NotionClient(token="dry-run")
    results = ingest_ics_to_notion(
        client,
        db_id=db_id or "dry-run-db",
        ics_path=args.file,
        category=args.category,
        dry_run=args.dry_run,
    )
    if args.json:
        _print_json(results)
        return
    for r in results:
        prefix = "[DRY-RUN] " if r.get("dry_run") else ""
        print(f"{prefix}Ingested event: {r['summary']} ({r.get('start', r.get('id', ''))})")


def cmd_ingest_git(args: argparse.Namespace) -> None:
    if not args.page_id and not args.dry_run:
        raise ConfigError("Provide --page-id to append the git activity digest.")
    client = NotionClient() if not args.dry_run else NotionClient(token="dry-run")
    res = ingest_git_to_notion(
        client,
        page_id=args.page_id or "dry-run-page",
        repo_path=args.repo,
        since=args.since,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(res["markdown"])
        return
    print(f"Appended {res['commit_count']} commit(s) ({res['blocks_added']} blocks) to {res['page_id']}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notion-os",
        description="Agent-first Notion Life OS CLI, schema bootstrapper, and automation kit.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth", help="Save your Notion integration token securely")
    p_auth.add_argument("--token", help="Notion token (omit for interactive prompt)")
    p_auth.set_defaults(func=cmd_auth)

    p_who = sub.add_parser("whoami", help="Show connected Notion bot and workspace")
    p_who.add_argument("--json", action="store_true")
    p_who.set_defaults(func=cmd_whoami)

    p_search = sub.add_parser("search", help="Search pages and databases")
    p_search.add_argument("query", nargs="?", default="")
    p_search.add_argument("--type", choices=["all", "page", "database"], default="all")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--compact", action="store_true", help="Token-efficient output for AI agents")
    p_search.add_argument("--json", action="store_true")
    p_search.set_defaults(func=cmd_search)

    p_read = sub.add_parser("read", help="Read a page as Markdown")
    p_read.add_argument("page_id")
    p_read.add_argument("--recursive", "-r", action="store_true", help="Fetch nested blocks recursively")
    p_read.add_argument("--depth", type=int, default=3)
    p_read.add_argument("--compact", action="store_true", help="Token-efficient output for AI agents")
    p_read.add_argument("--json", action="store_true")
    p_read.set_defaults(func=cmd_read)

    p_append = sub.add_parser("append", help="Append Markdown text/tasks to a page")
    p_append.add_argument("page_id")
    p_append.add_argument("text")
    p_append.set_defaults(func=cmd_append)

    p_push = sub.add_parser("push", help="Push a local Markdown file to a Notion page")
    p_push.add_argument("page_id")
    p_push.add_argument("file", help="Path to local Markdown file")
    p_push.add_argument("--dry-run", action="store_true")
    p_push.set_defaults(func=cmd_push)

    p_create = sub.add_parser("create-page", help="Create a child page or database row")
    p_create.add_argument("--parent-id", required=True)
    p_create.add_argument("--parent-type", choices=["page", "database"], default="page")
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--icon", help="Emoji icon")
    p_create.add_argument("--text", default="", help="Markdown content")
    p_create.add_argument("--json", action="store_true")
    p_create.set_defaults(func=cmd_create_page)

    p_dbq = sub.add_parser("db-query", help="Query rows from a Notion database")
    p_dbq.add_argument("db_id")
    p_dbq.add_argument("--filter", help="JSON filter payload")
    p_dbq.add_argument("--limit", type=int, default=50)
    p_dbq.add_argument("--json", action="store_true")
    p_dbq.set_defaults(func=cmd_db_query)

    p_raw = sub.add_parser("raw", help="Make a raw Notion REST API request")
    p_raw.add_argument("method", help="GET, POST, PATCH, DELETE")
    p_raw.add_argument("endpoint", help="e.g. /pages or /databases/<id>/query")
    p_raw.add_argument("--data", help="JSON request body")
    p_raw.set_defaults(func=cmd_raw)

    p_init = sub.add_parser("init", help="Bootstrap a Life OS workspace from a JSON schema template")
    p_init.add_argument("--template", required=True, help="Path to schema JSON template")
    p_init.add_argument("--parent-id", help="Parent Notion page ID where the Hub will be created")
    p_init.add_argument("--manifest", help="Path to write workspace manifest JSON")
    p_init.add_argument("--dry-run", action="store_true", help="Preview creation plan without calling API")
    p_init.add_argument("--json", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_brief = sub.add_parser("brief", help="Generate daily briefing (upcoming events + open tasks)")
    p_brief.add_argument("--calendar-db", help="Calendar database ID (defaults to manifest)")
    p_brief.add_argument("--page-id", action="append", help="Page ID(s) to scan for open to-dos")
    p_brief.add_argument("--days", type=int, default=7, help="Lookahead window in days")
    p_brief.add_argument("--manifest", help="Path to workspace manifest JSON")
    p_brief.add_argument("--compact", action="store_true", help="Token-efficient output for AI agents")
    p_brief.add_argument("--json", action="store_true")
    p_brief.set_defaults(func=cmd_brief)

    p_exp = sub.add_parser("export", help="Recursively export a Notion page tree to Markdown")
    p_exp.add_argument("page_id")
    p_exp.add_argument("--out", default="./exports", help="Output directory")
    p_exp.add_argument("--depth", type=int, default=3)
    p_exp.set_defaults(func=cmd_export)

    p_ingest = sub.add_parser("ingest", help="Ingest external data (ICS, Git) into Notion")
    ingest_sub = p_ingest.add_subparsers(dest="ingest_cmd", required=True)

    p_ics = ingest_sub.add_parser("ics", help="Import events from an `.ics` calendar file")
    p_ics.add_argument("file", help="Path to `.ics` file")
    p_ics.add_argument("--calendar-db", help="Target Notion Calendar DB ID")
    p_ics.add_argument("--category", default="Event")
    p_ics.add_argument("--manifest", help="Path to workspace manifest JSON")
    p_ics.add_argument("--dry-run", action="store_true")
    p_ics.add_argument("--json", action="store_true")
    p_ics.set_defaults(func=cmd_ingest_ics)

    p_git = ingest_sub.add_parser("git", help="Append recent git commits as a Markdown digest")
    p_git.add_argument("--repo", default=".", help="Path to git repository")
    p_git.add_argument("--since", default="1 day ago", help="Git --since window")
    p_git.add_argument("--page-id", help="Target Notion page ID")
    p_git.add_argument("--dry-run", action="store_true")
    p_git.set_defaults(func=cmd_ingest_git)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ConfigError, NotionAPIError, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
