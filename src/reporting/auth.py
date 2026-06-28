"""OAuth2 credentials for the Gmail reporting step.

`build_credentials` loads `token.json` (refreshing if expired) or returns None when
no token file exists (so the caller can no-op). `cmd_auth` runs the one-time
installed-app OAuth flow. Verified shapes in SDK_REFERENCE_gmail.md §2–§4.
"""
from __future__ import annotations

import json
import os

# Minimal scope: send only (assignment §6 cyber hygiene).
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def build_credentials(credentials_path, token_path, *, scopes=SCOPES):
    """Load token.json (refresh if expired); return None if no token file.

    Returns None when `token_path` does not exist so the caller can no-op
    (gating rule). Never raises into the orchestrator — the caller wraps in
    try/except (fail-soft).
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not os.path.exists(token_path):
        return None
    with open(token_path) as fh:
        creds = Credentials.from_authorized_user_info(json.load(fh), scopes=scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as fh:
            fh.write(creds.to_json())
    return creds


def cmd_auth(credentials_path, token_path, *, scopes=SCOPES) -> None:  # pragma: no cover
    """One-time installed-app OAuth login: writes token.json from credentials.json.

    Opens a browser for consent (port=0 -> OS picks a free port). Manual operator
    step (AC9); not exercised by tests (no credentials.json in CI).
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    os.makedirs(os.path.dirname(token_path) or ".", exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes=scopes)
    creds = flow.run_local_server(port=0)
    with open(token_path, "w") as fh:
        fh.write(creds.to_json())
    print(f"Token written to {token_path}")
