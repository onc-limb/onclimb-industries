#!/usr/bin/env python3
"""Google Tasks MCP server (self-built; depends on official SDKs only).

Push-mirror backend for jarvis-todo-management
(design: docs/todo-management-redesign-2026-07-02.md §4.7).
Exposes the minimal tool set for one-way sync (internal ledger -> Google Tasks).

Auth: OAuth 2.0 installed-app flow. Run auth.py once beforehand; this server
only loads/refreshes the saved token and never starts an interactive flow
(the stdio transport must stay clean — no prompts, no browser).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

CONFIG_DIR = Path(
    os.environ.get("GOOGLE_TASKS_MCP_CONFIG", "~/.config/google-tasks-mcp")
).expanduser()
TOKEN_PATH = CONFIG_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/tasks"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

mcp = FastMCP("google-tasks")
_service = None


def get_service():
    global _service
    if _service is not None:
        return _service
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"token not found: {TOKEN_PATH}. "
            "Run `python3 auth.py` in mcp-servers/google-tasks/ first (see README.md)."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)
    _service = build("tasks", "v1", credentials=creds, cache_discovery=False)
    return _service


def to_rfc3339(due: str) -> str:
    """Google Tasks API expects an RFC 3339 timestamp (date part only is kept)."""
    if DATE_RE.match(due):
        return f"{due}T00:00:00.000Z"
    return due


def slim_tasklist(tl: dict) -> dict:
    return {"id": tl["id"], "title": tl.get("title", "")}


def slim_task(t: dict) -> dict:
    return {
        "id": t["id"],
        "title": t.get("title", ""),
        "status": t.get("status"),
        "due": t.get("due"),
        "notes": t.get("notes"),
        "updated": t.get("updated"),
    }


@mcp.tool()
def list_tasklists() -> list[dict]:
    """List all Google Tasks task lists (id and title)."""
    service = get_service()
    items, page_token = [], None
    while True:
        resp = service.tasklists().list(maxResults=100, pageToken=page_token).execute()
        items.extend(slim_tasklist(tl) for tl in resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return items


@mcp.tool()
def create_tasklist(title: str) -> dict:
    """Create a new task list (one list per project). Returns its id and title."""
    service = get_service()
    tl = service.tasklists().insert(body={"title": title}).execute()
    return slim_tasklist(tl)


@mcp.tool()
def create_task(
    tasklist_id: str,
    title: str,
    notes: str | None = None,
    due: str | None = None,
) -> dict:
    """Create a task in a list. due accepts YYYY-MM-DD. Returns the task incl. its id."""
    service = get_service()
    body: dict = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = to_rfc3339(due)
    task = service.tasks().insert(tasklist=tasklist_id, body=body).execute()
    return slim_task(task)


@mcp.tool()
def update_task(
    tasklist_id: str,
    task_id: str,
    title: str | None = None,
    notes: str | None = None,
    due: str | None = None,
    status: str | None = None,
) -> dict:
    """Patch a task. status is 'needsAction' or 'completed'. due accepts YYYY-MM-DD."""
    if status is not None and status not in ("needsAction", "completed"):
        raise ValueError("status must be 'needsAction' or 'completed'")
    body: dict = {}
    if title is not None:
        body["title"] = title
    if notes is not None:
        body["notes"] = notes
    if due is not None:
        body["due"] = to_rfc3339(due)
    if status is not None:
        body["status"] = status
    if not body:
        raise ValueError("nothing to update (pass title/notes/due/status)")
    service = get_service()
    task = service.tasks().patch(tasklist=tasklist_id, task=task_id, body=body).execute()
    return slim_task(task)


@mcp.tool()
def list_tasks(tasklist_id: str, show_completed: bool = False) -> list[dict]:
    """List tasks in a list (open tasks by default; used for sync verification)."""
    service = get_service()
    items, page_token = [], None
    while True:
        resp = (
            service.tasks()
            .list(
                tasklist=tasklist_id,
                maxResults=100,
                pageToken=page_token,
                showCompleted=show_completed,
                showHidden=show_completed,
            )
            .execute()
        )
        items.extend(slim_task(t) for t in resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return items


if __name__ == "__main__":
    mcp.run()
