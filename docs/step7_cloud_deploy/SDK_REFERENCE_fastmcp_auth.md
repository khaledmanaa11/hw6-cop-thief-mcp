# SDK Ground-Truth — FastMCP v3 Auth & Docker for Step 7 (Cloud Deploy)

Verified via context7 (`/websites/gofastmcp`) **and live-checked against the installed
`fastmcp 3.4.2`** in this project's `.venv` on 2026-06-27. Every API shape below was
executed, not guessed. **This file is authoritative for the Step 7 Developer — copy from
here; do not invent API shapes.**

> Live verification commands used (all passed):
> - `FastMCP("cop", auth=verifier)` constructs; `m.auth` is the verifier instance.
> - `TokenVerifier.verify_token(self, token: str) -> AccessToken | None` (source-inspected).
> - `AccessToken` required fields: `token`, `client_id`, `scopes` (from `mcp.server.auth.provider`).
> - `verify_token` returning `AccessToken` ⇒ authorized; returning `None` ⇒ HTTP 401.
> - `mcp.run(transport="http", host=..., port=...)` is unchanged by attaching `auth`.

---

## §1 — FastMCP Client: sending a bearer token to a remote HTTP server

### §1.1 String shorthand (CONFIRMED)

Pass the raw token string to `auth=`. FastMCP automatically sends `Authorization: Bearer <token>`.

```python
from fastmcp import Client

async with Client(
    "https://your-server.example.com/mcp",
    auth="<your-token>",           # FastMCP adds the "Bearer " prefix automatically
) as client:
    await client.ping()
```

This is the pattern `HttpGateway` uses when `auth_token` is set. Source:
https://gofastmcp.com/clients/auth/bearer

### §1.2 Explicit BearerAuth class (CONFIRMED, alternative)

```python
from fastmcp.client.auth import BearerAuth
async with Client("https://.../mcp", auth=BearerAuth(token="<your-token>")) as client:
    ...
```

### §1.3 What HttpGateway does (Step 7 change)

`HttpGateway` stores an `auth_token` and overrides `__aenter__` to pass `auth=` when set:

```python
# gateway.py — HttpGateway
def __init__(self, url, name, telemetry, auth_token: str | None = None) -> None:
    super().__init__(url, name, telemetry)
    self._auth_token = auth_token

async def __aenter__(self) -> "HttpGateway":
    if self._auth_token:
        self._ctx = Client(self._transport, auth=self._auth_token)
    else:
        self._ctx = Client(self._transport)   # unchanged from today
    self._client = await self._ctx.__aenter__()
    return self
```

When `auth_token=None` (no env set), behaviour is identical to the existing code.

---

## §2 — FastMCP Server: static bearer-token auth gate (CONFIRMED on 3.4.2)

**Chosen approach: a native FastMCP `TokenVerifier` subclass passed via `FastMCP(name, auth=...)`.**
This keeps `mcp.run(transport="http", ...)` exactly as it is today — no `uvicorn` bootstrap,
no ASGI surgery.

> **Rejected alternative — Starlette `BaseHTTPMiddleware` on `mcp.http_app()`.**
> `mcp.http_app()` does exist on 3.4.2, but `BaseHTTPMiddleware` is a documented footgun for
> **streaming / SSE responses**, and MCP streamable-HTTP is a streaming transport. Wrapping the
> MCP app in `BaseHTTPMiddleware` risks corrupting the transport at deploy time, and it would
> force replacing `mcp.run()` with a hand-rolled `uvicorn.run()`. The native verifier integrates
> at the correct layer and was verified to work — do NOT use the middleware path.

### §2.1 The static verifier (CONFIRMED)

```python
import secrets
from fastmcp.server.auth import TokenVerifier
from mcp.server.auth.provider import AccessToken


class StaticBearerVerifier(TokenVerifier):
    """Accept exactly one static bearer token; reject everything else (-> HTTP 401)."""

    def __init__(self, token: str) -> None:
        super().__init__()                       # AuthProvider init (base_url etc. all optional)
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token.encode("utf-8"), self._token.encode("utf-8")):
            return AccessToken(token=token, client_id="static-bearer", scopes=[])
        return None                              # None -> 401 Unauthorized
```

Verified facts (executed against fastmcp 3.4.2):
- `TokenVerifier` import path: `from fastmcp.server.auth import TokenVerifier`.
- `verify_token` signature: `async def verify_token(self, token: str) -> AccessToken | None`.
- `AccessToken` import path: `from mcp.server.auth.provider import AccessToken`.
- `AccessToken` **required** fields: `token: str`, `client_id: str`, `scopes: list[str]`
  (others — `expires_at`, `resource`, `subject`, `claims` — default to `None`).
- `super().__init__()` with no args is valid (`base_url`, `required_scopes`,
  `resource_base_url` are all optional).
- Returning `None` ⇒ FastMCP responds **HTTP 401**.

### §2.2 Attaching it to the server (CONFIRMED)

```python
from fastmcp import FastMCP

mcp = FastMCP("cop", auth=verifier)   # auth=None means open server (today's behaviour)
```

`FastMCP("cop", auth=None)` is identical to `FastMCP("cop")` — so a `None` verifier keeps the
existing 152 tests and local runs unchanged.

### §2.3 `build_auth` and `build_*_server` signatures

```python
# src/mcp_servers/auth.py
def build_auth(token: str | None) -> StaticBearerVerifier | None:
    """Return a verifier when token is set, else None (open server)."""
    if not token:
        return None
    return StaticBearerVerifier(token)
```

```python
# cop_server.py / thief_server.py — builders gain an optional, backward-compatible param
def build_cop_server(config, auth_token: str | None = None) -> FastMCP:
    mcp = FastMCP("cop", auth=build_auth(auth_token))
    ...   # tool definitions unchanged
```

`build_cop_server(config)` still works (auth defaults to `None`).

---

## §3 — Server binding: `mcp.run()` with `$PORT` for Cloud Run (CONFIRMED)

```python
import os

if __name__ == "__main__":
    config = load_config("config.yaml")
    mcp = build_cop_server(config, auth_token=os.environ.get("COP_AUTH_TOKEN"))

    _env_port = os.environ.get("PORT")               # Cloud Run injects PORT
    _port = int(_env_port) if _env_port else config.servers.cop.port
    _host = "0.0.0.0" if _env_port else config.servers.cop.host

    mcp.run(transport="http", host=_host, port=_port)
```

- `mcp.run(transport="http", host="0.0.0.0", port=<int>)` — CONFIRMED.
- `host="0.0.0.0"` is required for Cloud Run to route external traffic.
- Cloud Run always injects `PORT` (default 8080); never hard-code it in source.
- No `uvicorn` import needed — `mcp.run()` runs the ASGI server internally.

---

## §4 — uv-based Dockerfile (CONFIRMED pattern)

```dockerfile
FROM python:3.11-slim

# Bring in the uv binary from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Layer-cache: copy manifests first; only rebuilds when deps change
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source after deps (better cache layering)
COPY src/ ./src/
COPY config.yaml ./

# Cyber hygiene: non-root user
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app
USER appuser

# Put venv python on PATH; Cloud Run injects PORT at runtime
ENV PATH="/app/.venv/bin:$PATH"
ENV MCP_ROLE=cop

# Dispatch: MCP_ROLE=cop -> cop_server, MCP_ROLE=thief -> thief_server
CMD ["sh", "-c", "exec python -m src.mcp_servers.${MCP_ROLE}_server"]
```

- `uv sync --frozen` guarantees reproducible installs from `uv.lock`; `--no-dev` excludes test/lint tools.
- `exec` in CMD makes Python PID 1 (receives SIGTERM correctly).
- `MCP_ROLE` default is `cop`; override to `thief` in the Cloud Run service env.

---

## §5 — Version pins

No new dependency pins needed. Already installed:
- `fastmcp>=3.4.2` — server/client + the `TokenVerifier`/`AccessToken` auth types.
- `mcp` (transitive) — provides `mcp.server.auth.provider.AccessToken`.
- `uvicorn[standard]` — used internally by `mcp.run(transport="http")`.

Do NOT add `starlette` or `uvicorn` imports to the server source — `mcp.run()` handles serving.

---

## §6 — Resolution log (no remaining BEST-EFFORT items)

All items the first draft flagged as unconfirmed were resolved by live inspection of
`fastmcp 3.4.2` in `.venv` on 2026-06-27:

| Item | Resolution |
|------|-----------|
| `TokenVerifier.verify_token()` return type | `AccessToken \| None` (source-inspected). Return `AccessToken(token=…, client_id="static-bearer", scopes=[])` on success, `None` on failure. |
| `AccessToken` import path + fields | `from mcp.server.auth.provider import AccessToken`; required: `token`, `client_id`, `scopes`. |
| `FastMCP(name, auth=verifier)` accepts a custom verifier | Confirmed — constructs; `m.auth` holds the instance. |
| Starlette `BaseHTTPMiddleware` path | **Rejected** (streaming/SSE footgun); native verifier used instead. |

Official docs: https://gofastmcp.com/servers/auth/authentication ·
https://gofastmcp.com/clients/auth/bearer
