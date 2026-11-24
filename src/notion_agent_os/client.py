"""Zero-dependency Notion REST API client with pagination, retry, and recursion."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import get_token

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


class NotionAPIError(RuntimeError):
    """Raised when the Notion API returns an HTTP error."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"[HTTP {status}] {code}: {message}")


class NotionClient:
    """Lightweight stdlib Notion REST API client."""

    def __init__(
        self,
        token: str | None = None,
        notion_version: str = NOTION_VERSION,
        base_url: str = BASE_URL,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self._token = token
        self.notion_version = notion_version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def token(self) -> str:
        if not self._token:
            self._token = get_token()
        return self._token

    def request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request against the Notion API with 429 retry handling."""
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8") if payload is not None else None

        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                url, data=data, headers=headers, method=method.upper()
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < self.max_retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = float(retry_after) if retry_after else float(attempt + 1)
                    time.sleep(min(delay, 10.0))
                    continue

                body = exc.read().decode("utf-8", errors="replace")
                try:
                    err_json = json.loads(body)
                    code = str(err_json.get("code", "api_error"))
                    msg = str(err_json.get("message", body))
                except Exception:
                    code = "http_error"
                    msg = body
                raise NotionAPIError(exc.code, code, msg) from exc

        raise NotionAPIError(429, "rate_limited", "Exceeded maximum retry attempts.")

    def whoami(self) -> dict[str, Any]:
        return self.request("GET", "/users/me")

    def search(
        self,
        query: str = "",
        obj_type: str = "all",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(results) < limit:
            page_size = min(100, limit - len(results))
            payload: dict[str, Any] = {"page_size": page_size}
            if query:
                payload["query"] = query
            if obj_type in ("page", "database"):
                payload["filter"] = {"value": obj_type, "property": "object"}
            if cursor:
                payload["start_cursor"] = cursor
            res = self.request("POST", "/search", payload)
            results.extend(res.get("results", []))
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return results[:limit]

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self.request("GET", f"/pages/{page_id}")

    def get_database(self, db_id: str) -> dict[str, Any]:
        return self.request("GET", f"/databases/{db_id}")

    def get_block_children(
        self,
        block_id: str,
        recursive: bool = False,
        max_depth: int = 4,
        _depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch all paginated child blocks, optionally recursing into nested blocks."""
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            qs = "?page_size=100"
            if cursor:
                qs += f"&start_cursor={urllib.parse.quote(cursor)}"
            res = self.request("GET", f"/blocks/{block_id}/children{qs}")
            batch = res.get("results", [])
            blocks.extend(batch)
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")

        if recursive and _depth < max_depth:
            for block in blocks:
                btype = block.get("type", "")
                if block.get("has_children") and btype not in (
                    "child_page",
                    "child_database",
                ):
                    block["_children"] = self.get_block_children(
                        block["id"],
                        recursive=True,
                        max_depth=max_depth,
                        _depth=_depth + 1,
                    )
        return blocks

    def append_blocks(
        self,
        block_id: str,
        children: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Append blocks in chunks of 100 (Notion API limit)."""
        created: list[dict[str, Any]] = []
        for i in range(0, len(children), 100):
            chunk = children[i : i + 100]
            res = self.request(
                "PATCH", f"/blocks/{block_id}/children", {"children": chunk}
            )
            created.extend(res.get("results", []))
        return created

    def create_page(
        self,
        parent_id: str,
        title: str,
        parent_type: str = "page",
        children: list[dict[str, Any]] | None = None,
        icon_emoji: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parent_key = "database_id" if parent_type == "database" else "page_id"
        props = dict(properties) if properties else {}
        if "title" not in props and parent_type == "page":
            props["title"] = {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        payload: dict[str, Any] = {
            "parent": {parent_key: parent_id},
            "properties": props,
        }
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}

        initial_children = children[:100] if children else None
        if initial_children:
            payload["children"] = initial_children

        page = self.request("POST", "/pages", payload)
        if children and len(children) > 100:
            self.append_blocks(page["id"], children[100:])
        return page

    def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: dict[str, Any],
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
        return self.request("POST", "/databases", payload)

    def query_database(
        self,
        db_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(results) < limit:
            payload: dict[str, Any] = {"page_size": min(100, limit - len(results))}
            if filter_obj:
                payload["filter"] = filter_obj
            if sorts:
                payload["sorts"] = sorts
            if cursor:
                payload["start_cursor"] = cursor
            res = self.request("POST", f"/databases/{db_id}/query", payload)
            results.extend(res.get("results", []))
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return results[:limit]


def extract_title(item: dict[str, Any]) -> str:
    """Extract plain title string from a Notion page or database object."""
    obj = item.get("object")
    if obj == "database":
        t = item.get("title", [])
        return "".join(x.get("plain_text", "") for x in t) or "(Untitled Database)"
    props = item.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            t = prop.get("title", [])
            return "".join(x.get("plain_text", "") for x in t) or "(Untitled Page)"
    return "(Untitled)"
