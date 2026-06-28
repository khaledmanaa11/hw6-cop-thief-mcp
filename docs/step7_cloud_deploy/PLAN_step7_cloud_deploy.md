# PLAN — Step 7: Cloud Distributed Deployment

- **Status:** triplet-built
- **Source:** `DECISION_step7_cloud_deploy.md`, `SDK_REFERENCE_fastmcp_auth.md`,
  `PRD_step7_cloud_deploy.md`

---

## 1. Architecture overview

Step 7 is purely infrastructure: it does not change game logic, strategies, agents, prompts,
or the GUI. It adds a security/transport layer around the existing two FastMCP servers and
extends the orchestrator's gateway to speak to remote HTTPS endpoints.

```
  ┌──────────────────────── CLIENT-SIDE (unchanged) ─────────────────────────────┐
  │                                                                               │
  │  src/orchestrator/__main__.py                                                │
  │    gateway_from_env("cop", config, tel)  ──→  HttpGateway(COP_SERVER_URL,   │
  │                                               auth_token=COP_AUTH_TOKEN)    │
  │    gateway_from_env("thief", config, tel) ─→  HttpGateway(THIEF_SERVER_URL, │
  │                                               auth_token=THIEF_AUTH_TOKEN)  │
  │                         ↓  Authorization: Bearer <token>  (HTTPS/TLS)       │
  └──────────────────────────────────────────────────────────────────────────────┘
                              ↓  internet / Cloud Run TLS
  ┌── CLOUD (Google Cloud Run) ────────────────────────────────────────────────┐
  │                                                                            │
  │  Service: hw6-cop (MCP_ROLE=cop, PORT=8080)                               │
  │    Dockerfile → python -m src.mcp_servers.cop_server                      │
  │    Auth gate (FastMCP TokenVerifier): COP_AUTH_TOKEN env                  │
  │    Binding: 0.0.0.0:$PORT                                                 │
  │                                                                            │
  │  Service: hw6-thief (MCP_ROLE=thief, PORT=8080)                           │
  │    Dockerfile → python -m src.mcp_servers.thief_server                    │
  │    Auth gate (FastMCP TokenVerifier): THIEF_AUTH_TOKEN env                │
  │    Binding: 0.0.0.0:$PORT                                                 │
  └────────────────────────────────────────────────────────────────────────────┘
```

**Key invariant:** the LLM, orchestrator, referee, and agents stay on the operator's
machine. Only the two stateless tool-servers go to the cloud.

---

## 2. File / module layout

```
Dockerfile                                  (new)   — single image, MCP_ROLE dispatch
.dockerignore                               (new)   — exclude runs/, .env, caches
.env.example                                (new)   — document env contract (no values)
.gitignore                                  (verify) — .env and runs/ already present
src/mcp_servers/auth.py                     (new)   — build_auth() → TokenVerifier | None
src/mcp_servers/cop_server.py               (edit)  — builder auth_token param + __main__ PORT
src/mcp_servers/thief_server.py             (edit)  — builder auth_token param + __main__ PORT
src/orchestrator/gateway.py                 (edit)  — HttpGateway auth_token + from_env()
src/orchestrator/__main__.py                (edit)  — use gateway_from_env() helper
deploy/deploy.sh                            (new)   — thin gcloud wrapper (optional)
docs/step7_cloud_deploy/DEPLOY.md           (new)   — full copy-paste runbook
tests/test_cloud/__init__.py                (new)   — package marker
tests/test_cloud/test_auth.py               (new)   — offline auth 401/200 tests
tests/test_cloud/test_gateway.py            (new)   — HttpGateway header + env wiring
tests/test_cloud/test_static_guards.py      (new)   — grep/line-count/secret guard
```

No changes to `config.yaml` (no new keys for secrets/URLs — they live in env).
No changes to `pyproject.toml` (all required deps already present).
No changes to `src/game/`, `src/strategy/`, `src/agents/`, `src/gui/`.

---

## 3. Data model / key structures

### Env contract (single source of truth — lives in `.env` / Cloud Run service config)

| Env var | Side | Meaning |
|---------|------|---------|
| `MCP_ROLE` | Server (container) | `cop` or `thief`; selects which server module to run |
| `PORT` | Server (container) | Injected by Cloud Run; server binds `0.0.0.0:$PORT` |
| `COP_AUTH_TOKEN` | Server (cop) + Client | Static bearer token for the Cop MCP server |
| `THIEF_AUTH_TOKEN` | Server (thief) + Client | Static bearer token for the Thief MCP server |
| `COP_SERVER_URL` | Client only | Public HTTPS URL of the cop service (incl. `/mcp`) |
| `THIEF_SERVER_URL` | Client only | Public HTTPS URL of the thief service (incl. `/mcp`) |

**Never** put token values in `config.yaml`, `src/`, or any committed file.

### `build_auth(token: str | None)` return contract

- `None` → no auth; `FastMCP(name, auth=None)` runs open (for local dev and in-memory tests)
- `StaticBearerVerifier` instance → passed to `FastMCP(name, auth=verifier)`; rejects bad tokens with 401

### `HttpGateway` updated constructor

```python
HttpGateway(
    url: str,
    name: str,
    telemetry: Telemetry,
    auth_token: str | None = None,   # NEW; default None = no header = unchanged behaviour
)
```

---

## 4. Component design

### `src/mcp_servers/auth.py`

- **Responsibility:** provide a self-contained, offline-testable bearer-token auth gate.
  Has no dependency on game logic, agents, or config. ≤ 50 lines.
- **Key types:**
  - `StaticBearerVerifier(TokenVerifier)` — FastMCP token verifier. `verify_token(token)`
    compares with `secrets.compare_digest` and returns `AccessToken(token=…,
    client_id="static-bearer", scopes=[])` on match, `None` on mismatch (FastMCP turns
    `None` into HTTP 401). Imports: `TokenVerifier` from `fastmcp.server.auth`,
    `AccessToken` from `mcp.server.auth.provider`.
- **Key functions:**
  - `build_auth(token: str | None) -> StaticBearerVerifier | None`
    Returns a verifier instance when token is set, or `None` when token is `None`/empty.
    The server builder passes it straight to `FastMCP(name, auth=build_auth(token))`.
- **Why the native `TokenVerifier` (not Starlette `BaseHTTPMiddleware`):** the verifier
  integrates at FastMCP's own auth layer and was live-verified against the installed
  `fastmcp 3.4.2` (see `SDK_REFERENCE §2`). It keeps `mcp.run(transport="http", …)`
  completely unchanged. The Starlette-middleware alternative is **rejected**: wrapping the
  MCP app in `BaseHTTPMiddleware` is a known footgun for streaming/SSE responses (MCP
  streamable-HTTP is a streaming transport) and would force a hand-rolled `uvicorn.run()`.
- **Security:** uses `secrets.compare_digest` (constant-time comparison) to prevent
  timing attacks. Tokens are never printed or logged.

### `src/mcp_servers/cop_server.py` / `thief_server.py` — builder + `__main__`

- `build_cop_server` / `build_thief_server` gain an optional `auth_token: str | None = None`
  param and pass `auth=build_auth(auth_token)` into `FastMCP(...)`. Tool definitions and
  `return mcp` are untouched. `build_*_server(config)` (no token) ⇒ `auth=None` ⇒ open
  server — identical to today, so the existing Step-2/3 tests keep passing.
- `__main__` gains:
  - `import os` and `from src.mcp_servers.auth import build_auth`
  - Pass `auth_token=os.environ.get("COP_AUTH_TOKEN")` (or `THIEF_AUTH_TOKEN`) into the builder
  - Read `PORT` from env; when set use `0.0.0.0:$PORT`, else use `config.servers.<role>.host:port`
  - Keep `mcp.run(transport="http", host=host, port=port)` exactly as today — no `uvicorn`/`http_app`
- **Backward compatibility guarantee:** `InMemoryGateway` tests never touch `__main__`, and
  `build_*_server(config)` still defaults to an open server.

### `src/orchestrator/gateway.py` — `HttpGateway` and `gateway_from_env`

- **`HttpGateway.__init__`** gains `auth_token: str | None = None` (default preserves
  existing callers). Stores `self._auth_token`.
- **`HttpGateway.__aenter__`** overrides `_BaseGateway.__aenter__`: when `auth_token` is
  set uses `Client(url, auth=auth_token)` (CONFIRMED from context7, see SDK ref §1.1);
  when not set uses `Client(url)` identically to today.
- **`gateway_from_env(role: str, config, telemetry: Telemetry) -> HttpGateway`** (new module-
  level function): reads `{ROLE}_SERVER_URL` and `{ROLE}_AUTH_TOKEN` from env; falls back to
  `http://{config.servers.<role>.host}:{config.servers.<role>.port}/mcp` and `None` token.
  This makes `src/orchestrator/__main__.py` testable by patching env vars.

### `src/orchestrator/__main__.py`

- Replace the two inline URL-construction lines with calls to `gateway_from_env`.
- No other changes; all game/LLM/replay logic is untouched.

### `Dockerfile`

See `SDK_REFERENCE_fastmcp_auth.md §4` for the verified uv Docker pattern.
Key design points:
- `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv` — official uv binary
- `COPY pyproject.toml uv.lock ./` then `RUN uv sync --frozen --no-dev` — locked, no dev tools
- `COPY src/ ./src/` and `COPY config.yaml ./` — source after deps (layer cache)
- `RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app` + `USER appuser`
- `ENV PATH="/app/.venv/bin:$PATH"` and `ENV MCP_ROLE=cop`
- `CMD ["sh", "-c", "exec python -m src.mcp_servers.${MCP_ROLE}_server"]`

### `docs/step7_cloud_deploy/DEPLOY.md` runbook

Must cover: (a) prerequisites, (b) build + push image to GCR/Artifact Registry,
(c) `gcloud run deploy hw6-cop` with `MCP_ROLE=cop` + token env + `--port=8080`,
(d) `gcloud run deploy hw6-thief` with `MCP_ROLE=thief` + token env, (e) capture 2 URLs,
(f) curl smoke-test: `curl -i <URL>/mcp` → 401, `curl -H "Authorization: Bearer $TOK" <URL>/mcp`
→ 200, (g) `cloudflare tunnel` / `ngrok` fallback section for the no-billing case.

### `tests/test_cloud/`

Three test files, all offline (no live server, no cloud account):

1. **`test_auth.py`** — tests `StaticBearerVerifier` and `build_auth` directly (the
   `verify_token` coroutine runs under the project's `asyncio_mode=auto`):
   - `build_auth(None)` / `build_auth("")` return `None`; `build_auth("tok")` is a verifier
   - `verify_token(correct)` returns an `AccessToken`; `verify_token(wrong|"")` returns `None`
   - end-to-end: `build_cop_server(config).auth is None`, `build_cop_server(config, "tok").auth is not None`

2. **`test_gateway.py`** — tests `HttpGateway` auth and `gateway_from_env`:
   - Monkeypatch `fastmcp.Client.__init__` to capture `auth` kwarg; assert it equals token
   - `gateway_from_env` with env set reads URL and token; without env reads config+no-token
   - Binding helper: when `PORT` env is set, `host="0.0.0.0"` and `port=int(PORT)`;
     when unset, host and port come from config

3. **`test_static_guards.py`** — static code checks:
   - No file in `src/` or `config.yaml` contains `COP_AUTH_TOKEN=` or `THIEF_AUTH_TOKEN=`
     (would mean a committed secret value) or a `.run.app` URL
   - `auth.py` ≤ 150 lines
   - New `src/` files ≤ 150 lines each
   - `auth.py` does not import `src.game`, `src.orchestrator`, `src.strategy`, `src.agents`

---

## 5. Control flow / sequences

### Local run (unchanged behaviour, no env set)

```
python -m src.mcp_servers.cop_server
  → load_config("config.yaml")
  → os.environ.get("COP_AUTH_TOKEN")  # → None
  → build_cop_server(config, auth_token=None)
        → FastMCP("cop", auth=build_auth(None))   # auth=None → open server
  → os.environ.get("PORT")            # → None
  → host = config.servers.cop.host    # "127.0.0.1"
  → port = config.servers.cop.port    # 8001
  → mcp.run(transport="http", host="127.0.0.1", port=8001)   # IDENTICAL to today
```

### Cloud Run deployment (auth + PORT set)

```
Container starts: MCP_ROLE=cop, PORT=8080, COP_AUTH_TOKEN=<secret>
  → python -m src.mcp_servers.cop_server
  → load_config("config.yaml")
  → os.environ.get("COP_AUTH_TOKEN")  # → "<secret>"
  → build_cop_server(config, auth_token="<secret>")
        → FastMCP("cop", auth=StaticBearerVerifier("<secret>"))   # bad token → 401
  → os.environ.get("PORT")            # → "8080"
  → host = "0.0.0.0"
  → port = 8080
  → mcp.run(transport="http", host="0.0.0.0", port=8080)   # same call as local, env-aware host/port
```

### Orchestrator (cloud mode, env set)

```
operator sets: COP_SERVER_URL, THIEF_SERVER_URL, COP_AUTH_TOKEN, THIEF_AUTH_TOKEN
python -m src.orchestrator
  → gateway_from_env("cop", config, telemetry)
      reads COP_SERVER_URL → "https://hw6-cop-xxxx.run.app/mcp"
      reads COP_AUTH_TOKEN → "<secret>"
      returns HttpGateway("https://...", "cop", telemetry, auth_token="<secret>")
  → HttpGateway.__aenter__
      Client("https://...", auth="<secret>")   # sends Authorization: Bearer <secret>
```

---

## 6. Config additions

No new `config.yaml` keys. The env contract (URLs, tokens) lives entirely in environment
variables / `.env` / Cloud Run service configuration — never in `config.yaml` or source.

The `deploy:` block mentioned in DECISION §5 as an optional non-secret block (region,
service-name prefix) is **deferred** — it adds complexity with no graded value. The
runbook documents these as CLI flags.

---

## 7. Test strategy

- **Unit (offline):** `tests/test_cloud/test_auth.py` calls `StaticBearerVerifier.verify_token`
  directly (AccessToken on match, `None` on mismatch) and asserts the verifier attaches to the
  FastMCP server only when a token is set — no live server needed. `test_gateway.py` inspects
  how `HttpGateway` stores the token and how `gateway_from_env` resolves URL/token.
- **Static guards:** `test_static_guards.py` checks file sizes, no-secret grep, and no
  forbidden imports in `auth.py`.
- **Regression:** `uv run pytest -q` (the full existing 152-test suite) must continue
  passing — this is the primary backward-compat fence.
- **Manual acceptance:** `docker build` + `docker run` smoke-test; `gcloud run deploy` +
  two-URL curl proof (operator session, not automated).

---

## 8. Risks & mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FastMCP auth API differs from assumption | Low | Native `TokenVerifier`/`AccessToken`/`FastMCP(auth=…)` path was live-verified end-to-end on the installed `fastmcp 3.4.2` (SDK ref §2/§6); no `http_app`/middleware used |
| `uv sync --frozen` fails in Docker (platform mismatch) | Low | `uv.lock` already present and used in CI; `--frozen` enforces it; test with `docker buildx build --platform linux/amd64` |
| Cloud Run free-tier credit exhaustion | Low | `scale-to-zero` + `min-instances=0`; Developer session is short; runbook documents `gcloud billing accounts list` prerequisite |
| Token comparison timing attack | Very Low | `secrets.compare_digest` (constant-time) used; token never logged |
| Backward-compat regression in gateway | Medium | `auth_token` defaults to `None`; `_BaseGateway.__aenter__` only overridden in `HttpGateway`; `InMemoryGateway` unaffected; full suite is the fence |
| Docker not available on Developer's machine | Medium | Runbook includes `gcloud builds submit` (Cloud Build) as an alternative to local Docker |
| `.env` accidentally committed | Low | `.gitignore` already has `.env`; grep guard test checks for committed token shape |

---

## 9. Work breakdown (macro order)

1. **Hygiene first:** `.env.example`, verify `.gitignore`, create `.dockerignore`.
2. **`auth.py`:** implement `StaticBearerVerifier` and `build_auth` (50 lines max).
3. **Server builder + `__main__`:** cop then thief — `auth_token` param + env wiring + PORT binding.
4. **`HttpGateway` + `gateway_from_env`:** auth_token param + env-driven URL/token helper.
5. **`orchestrator/__main__.py`:** swap inline URL construction for `gateway_from_env`.
6. **`Dockerfile` + `.dockerignore`:** build artifact with verified uv pattern.
7. **`DEPLOY.md` runbook:** complete copy-paste gcloud commands + curl proof template.
8. **Tests:** `test_auth.py`, `test_gateway.py`, `test_static_guards.py` — all offline.
9. **Gate:** ruff, coverage, full suite, Docker smoke.
10. **Manual operator:** `gcloud auth login` → deploy → capture URLs → README.
