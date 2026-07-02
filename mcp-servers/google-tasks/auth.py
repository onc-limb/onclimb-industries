#!/usr/bin/env python3
"""One-time OAuth 2.0 authorization for the Google Tasks MCP server.

Interactive flows are kept out of server.py (its stdio transport must stay
clean), so run this once before registering the server:

    python3 auth.py

Prerequisite: ~/.config/google-tasks-mcp/credentials.json
(OAuth client ID of type "Desktop app", downloaded from Google Cloud Console.
See README.md for the GCP-side steps.)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

CONFIG_DIR = Path(
    os.environ.get("GOOGLE_TASKS_MCP_CONFIG", "~/.config/google-tasks-mcp")
).expanduser()
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/tasks"]


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        sys.exit(
            f"error: {CREDENTIALS_PATH} not found.\n"
            "Download the OAuth client (Desktop app) credentials from Google Cloud "
            "Console and place them there. See README.md."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    TOKEN_PATH.chmod(0o600)
    print(f"token saved: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
