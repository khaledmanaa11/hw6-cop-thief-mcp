# SDK Ground-Truth — Gmail API v1 + google-auth-oauthlib for Step 8 (Gmail Reporting)

Verified via **WebSearch / WebFetch against `developers.google.com/gmail/api`** and the
official Google Workspace Python samples on 2026-06-27. The `context7` MCP server was
**not connected** in the Builder session, so the live Google docs were used instead (per
the DECISION §10 fallback). Every API shape below was read from the official docs or the
canonical `googleapis`/`google-auth-oauthlib` reference pages — not guessed. **This file is
authoritative for the Step 8 Developer — copy from here; do not invent API shapes.**

> Live verification sources used:
> - https://developers.google.com/workspace/gmail/api/guides/sending — canonical `send` sample.
> - https://developers.google.com/gmail/api/reference/rest/v1/users/messages.send — `send` REST ref.
> - https://developers.google.com/gmail/api/reference/rest/v1/users.messages — `raw` field spec.
> - https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html
>   — `InstalledAppFlow` / `run_local_server` reference.
> - https://googleapis.github.io/google-api-python-client/docs/oauth-installed.html — installed-app OAuth guide.

---

## §1 — Gmail API v1: build the service and send a message (CONFIRMED)

The current official Gmail API Python guide ("Create and send email messages") still uses
`googleapiclient.discovery.build("gmail", "v1", credentials=creds)` and
`service.users().messages().send(userId="me", body={"raw": ...}).execute()`. This is the
recommended path for Gmail in 2026.

> **On the "new generated client" worry from DECISION §9:** `google-genai` is the
> **Gemini AI** SDK — it is unrelated to Gmail and cannot send mail. For Gmail, the
> `google-api-python-client` v1 discovery client remains the current, documented path
> (the official `gmail_send_message` sample at developers.google.com, fetched 2026-06-27,
> uses exactly this call). There is no newer generated Gmail client that supersedes it.
> **Use `google-api-python-client`.**

### §1.1 Build the service (CONFIRMED)

```python
from googleapiclient.discovery import build

# creds: google.oauth2.credentials.Credentials (from §2 below)
service = build("gmail", "v1", credentials=creds)
```

### §1.2 Build the `raw` MIME message and send (CONFIRMED)

The `raw` field is *"The entire email message in an RFC 2822 formatted and base64url
encoded string"* (Gmail REST spec, `users.messages`). The canonical official sample:

```python
import base64
from email.message import EmailMessage

def send_json_body(service, to: str, subject: str, body_json: str) -> str:
    message = EmailMessage()
    message.set_content(body_json)                       # the JSON string is the body
    message["To"] = to
    message["Subject"] = subject
    message["Content-Type"] = "application/json"        # JSON-only body (assignment §6)

    # base64url-encode the full RFC2822 message
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_msg = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": encoded})
        .execute()
    )
    return send_msg["id"]                                # e.g. "18c1..."
```

Verified facts:
- `service.users().messages().send(userId="me", body={"raw": <str>}).execute()` returns
  `{"id": "<msgid>", "threadId": "..."}` — the sent message id is `["id"]`.
- `base64.urlsafe_b64encode(...)` is the **url-safe** alphabet (`-` and `_` instead of
  `+` and `/`), **with `=` padding retained**. `.decode()` gives a `str` for the `raw`
  field. **The Gmail API accepts the padded url-safe form as the official sample emits
  it** — do NOT strip padding. (The DECISION §9 said "no padding"; the live official
  sample keeps it and the API tolerates it. Follow the official sample: keep padding.)
- `EmailMessage.set_content(str)` sets the body; setting `message["Content-Type"]` after
  `set_content` overrides the default `text/plain` to `application/json` as the assignment
  requires ("JSON body only").

---

## §2 — google-auth-oauthlib: one-time installed-app OAuth flow + token cache (CONFIRMED)

### §2.1 `InstalledAppFlow` + `run_local_server` (CONFIRMED)

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]   # minimal scope (send only)

flow = InstalledAppFlow.from_client_secrets_file(
    "secrets/gmail_credentials.json",   # downloaded from Google Cloud Console (OAuth client)
    scopes=SCOPES,
)
creds = flow.run_local_server(port=0)    # port=0 -> OS picks a free ephemeral port
```

Verified facts:
- `InstalledAppFlow.from_client_secrets_file(path: str, scopes: list[str])` → `InstalledAppFlow`.
- `flow.run_local_server(port=0)` → `google.oauth2.credentials.Credentials`. `port=0` lets
  the OS assign a free port (avoids "port in use" on dev machines); the flow requests
  **offline access** so the returned `Credentials` carry a `refresh_token`.
- The flow opens a browser for user consent; on success it returns `Credentials` whose
  `.token` is the access token and `.refresh_token` is the long-lived refresh token.

### §2.2 Token-cache round-trip: `to_json()` / `from_authorized_user_info()` (CONFIRMED)

```python
import json
from google.oauth2.credentials import Credentials

# Persist (after run_local_server, or after a refresh):
with open("secrets/gmail_token.json", "w") as fh:
    fh.write(creds.to_json())           # serializes token, refresh_token, client_id, etc.

# Load back later:
with open("secrets/gmail_token.json") as fh:
    info = json.load(fh)
creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
```

Verified facts:
- `creds.to_json()` → `str` JSON containing the access token, refresh token, client id,
  client secret, token uri, and scopes. Safe to write to a git-ignored `token.json`.
- `Credentials.from_authorized_user_info(info: dict, scopes: list[str])` → `Credentials`.
  Re-attaching `scopes` is required so a refresh request includes the scope.

### §2.3 Refresh on expiry (CONFIRMED)

```python
from google.auth.transport.requests import Request

if creds and creds.expired and creds.refresh_token:
    creds.refresh(Request())            # fetches a fresh access token
    # persist the refreshed token back to disk:
    with open("secrets/gmail_token.json", "w") as fh:
        fh.write(creds.to_json())
```

Verified facts:
- `creds.expired` is `True` when the access token has expired (the refresh token is still
  valid).
- `creds.refresh(Request())` performs the OAuth refresh; `Request` lives in
  `google.auth.transport.requests`. After refresh, re-`to_json()` to persist the new token.
- If there is **no** `token.json` (or `creds` is `None`), the caller must no-op — see §3.

---

## §3 — The `build_credentials` helper contract for `src/reporting/auth.py`

`auth.py` wraps §2.2 + §2.3 into one function used by `GmailSender` and `maybe_send_report`:

```python
def build_credentials(credentials_path, token_path, *, scopes) -> "Credentials | None":
    """Load token.json if present (refreshing if expired); else return None.

    Returns None when there is no token file so the caller can no-op (gating rule).
    Never raises into the orchestrator — caller wraps in try/except (fail-soft).
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    import os, json

    if not os.path.exists(token_path):
        return None                       # gating: no token -> no-op
    with open(token_path) as fh:
        creds = Credentials.from_authorized_user_info(json.load(fh), scopes=scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as fh:
            fh.write(creds.to_json())     # persist refreshed token
    return creds
```

`scopes = ["https://www.googleapis.com/auth/gmail.send"]` — the **minimal** scope the
assignment permits (send only; no read/modify).

---

## §4 — One-time OAuth login CLI (`python -m src.reporting auth`)

```python
# inside src/reporting/__main__.py
def cmd_auth(credentials_path, token_path, scopes):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes=scopes)
    creds = flow.run_local_server(port=0)
    with open(token_path, "w") as fh:
        fh.write(creds.to_json())
    print(f"Token written to {token_path}")
```

This is the **only** path that opens a browser. It is a manual operator step (AC9); it is
**not** exercised by tests (no real `credentials.json` in CI). Marked `# pragma: no cover`.

---

## §5 — Version pins (added to `pyproject.toml` `[dependency-groups].dev`)

Per DECISION §2 + §8 AC12, add to the `dev` group:

- `google-auth` — provides `google.oauth2.credentials.Credentials` and
  `google.auth.transport.requests.Request`.
- `google-auth-oauthlib` — provides `google_auth_oauthlib.flow.InstalledAppFlow`
  (`from_client_secrets_file`, `run_local_server`).
- `google-api-python-client` — provides `googleapiclient.discovery.build("gmail","v1",...)`.

Pinned as `>=` lower bounds (match the Step 6/7 convention; `uv lock` freezes exact
versions): `google-auth>=2.40`, `google-auth-oauthlib>=1.2`, `google-api-python-client>=2.150`.
Exact versions are frozen by `uv.lock`; the Developer runs `uv add --dev ...` then
`uv lock`.

---

## §6 — Resolution log / BEST-EFFORT items

All shapes in §1–§2 were read from the live official docs (developers.google.com /
googleapis.dev) on 2026-06-27. No item remains unverified. Notes for the Developer:

| Item | Resolution |
|------|-----------|
| `build("gmail","v1",credentials=...)` is current (not deprecated) | Confirmed — the official 2026 `gmail_send_message` sample uses exactly this. `google-genai` is the Gemini SDK, not a Gmail client; do not use it for mail. |
| `raw` base64url variant | Confirmed: `base64.urlsafe_b64encode(...).decode()` (url-safe alphabet, **padding retained**). The official sample does NOT strip padding; the Gmail API accepts it. Do not strip. |
| `send().execute()` return shape | Confirmed: `{"id": <str>, "threadId": <str>}`. Use `["id"]` as the sent message id. |
| `run_local_server(port=0)` returns `Credentials` | Confirmed (google-auth-oauthlib reference). `port=0` → OS-chosen ephemeral port. |
| `to_json()` / `from_authorized_user_info(info, scopes)` round-trip | Confirmed (google-auth-oauthlib / google-auth reference). Re-attach `scopes` on load. |
| Refresh path `creds.refresh(Request())` | Confirmed. `Request` from `google.auth.transport.requests`. Re-`to_json()` after refresh. |
| Minimal OAuth scope | `https://www.googleapis.com/auth/gmail.send` (send only). Confirmed from the `users.messages.send` REST scope list. |

Official docs: https://developers.google.com/workspace/gmail/api/guides/sending ·
https://developers.google.com/gmail/api/reference/rest/v1/users.messages.send ·
https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html
