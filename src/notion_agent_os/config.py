"""Configuration, token management, and local workspace manifest handling."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "notion-agent-os"
DEFAULT_TOKEN_FILE = CONFIG_DIR / "token"
LEGACY_TOKEN_FILE = Path.home() / ".config" / "notion" / "token"
DEFAULT_MANIFEST_FILE = CONFIG_DIR / "workspace.json"
LOCAL_MANIFEST_NAME = ".notion-os.json"


class ConfigError(RuntimeError):
    """Raised when required configuration (such as Notion token) is missing."""


def get_token(explicit_token: str | None = None) -> str:
    """Resolve Notion API token from explicit arg, env var, or config file."""
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    env_token = os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY")
    if env_token and env_token.strip():
        return env_token.strip()

    for path in (DEFAULT_TOKEN_FILE, LEGACY_TOKEN_FILE):
        if path.is_file():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token

    raise ConfigError(
        "Notion API token not found. Set NOTION_TOKEN or run `notion-os auth`."
    )


def save_token(token: str, path: Path = DEFAULT_TOKEN_FILE) -> Path:
    """Persist Notion API token securely with 0600 permissions."""
    cleaned = token.strip()
    if not cleaned:
        raise ConfigError("Token cannot be empty.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cleaned + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def resolve_manifest_path(explicit_path: str | Path | None = None) -> Path:
    """Return manifest path: explicit > local .notion-os.json > global config."""
    if explicit_path:
        return Path(explicit_path)
    local = Path.cwd() / LOCAL_MANIFEST_NAME
    if local.is_file():
        return local
    return DEFAULT_MANIFEST_FILE


def load_manifest(explicit_path: str | Path | None = None) -> dict[str, Any]:
    """Load workspace manifest (created by `notion-os init`)."""
    path = resolve_manifest_path(explicit_path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(data: dict[str, Any], path: str | Path | None = None) -> Path:
    """Save workspace manifest JSON."""
    target = Path(path) if path else DEFAULT_MANIFEST_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target
