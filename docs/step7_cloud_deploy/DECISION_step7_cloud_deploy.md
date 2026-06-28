# DECISION — Step 7: Cloud distributed deployment

- **Roadmap position:** step 7 of 8 (`step7_cloud_deploy`)
- **Date discussed:** 2026-06-27
- **Status:** decision-written
- **Assignment references:** §13 Table 4 (step 7: "Push MCP servers to cloud with tokens / secure tunnels / cyber hygiene; publish 2 public URLs"); cross-cutting server/client split (LLM stays in client).

## 1. What this step is (one paragraph)
Today both FastMCP servers (`src/mcp_servers/cop_server.py`, `thief_server.py`) run on
`127.0.0.1:8001/8002` over streamable-HTTP, and the orchestrator connects to them as a
local HTTP client. Step 7 makes the **two tool-servers genuinely remote**: each is packaged
as a container, deployed to **Google Cloud Run**, reachable at its own **public HTTPS URL**,
and gated by a **per-server bearer token**. The orchestrator + LLM + referee stay entirely
client-side — that is the binding constraint (the LLM lives in the client, the MCP server
only exposes tools). After this step the system is *distributed*: the brain on the operator's
machine talks to two independently-deployed, authenticated tool-servers over the public
internet, with TLS and no secrets in the repo.

## 2. What it adds to the project
- A single **`Dockerfile`** (uv-based) that runs either server, role chosen by env `MCP_ROLE=cop|thief`.
- A **bearer-token auth gate** on each server: requests without/with-wrong `Authorization: Bearer <token>` get 401; correct token gets through. Auth is **active only when the server's token env var is set** (local/in-memory runs stay open → existing tests unchanged).
- **Cloud-aware binding** in each server `__main__`: bind `0.0.0.0:$PORT` when Cloud Run injects `PORT`, else fall back to config `host:port`.
- **`HttpGateway` upgrade**: read the server's public URL + token from env, send the `Authorization` header, target `https://…/mcp`. Falls back to the config localhost URL with no token when env is unset.
- A **deploy runbook** `docs/step7_cloud_deploy/DEPLOY.md` and a thin deploy helper script (`deploy/deploy.sh` or documented `gcloud` commands).
- **Cyber-hygiene artifacts**: `.env.example` (token + URL shape), `.env` + `runs/` in `.gitignore`, non-root container `USER`, pinned deps via `uv.lock`, token never logged, a `ping`/health route Cloud Run can probe.
- **Tests** for the auth layer and env-driven wiring (401-without / 200-with, gateway header injection, binding fallback) — all runnable offline in CI.

## 3. Scope
**In scope:**
- Containerize the two existing MCP servers (no change to their tool surface or game rules).
- Per-server static bearer-token authentication, env-injected.
- Cloud Run binding contract (`0.0.0.0:$PORT`) with local fallback.
- Client-side (`HttpGateway`) auth-header + public-URL wiring via env.
- Deploy runbook + helper, `.env.example`, hygiene checklist, offline-testable auth/wiring tests.
- A **manual** final acceptance: actually `gcloud run deploy` both services and capture the 2 public URLs for the README (operator step — needs interactive `gcloud auth login`).

**Out of scope (deferred):**
- Any change to game logic, strategy, NL/LLM behavior, or the GUI.
- OAuth/JWT flows, per-user identity, rate limiting, secret-manager integration → not needed for the grade; bearer token + Cloud Run TLS satisfies "tokens / secure tunnels / cyber hygiene".
- Deploying the orchestrator/LLM to the cloud → it MUST stay client-side (constraint).
- Gmail report email → step 8.

## 4. Chosen approach (and what we rejected)
**Decision:** One uv-based container image (role via `MCP_ROLE`), deployed as **two Google
Cloud Run services**, each protected by its own **static bearer token** read from env, with
TLS provided by Cloud Run. The client (`HttpGateway`) reads each service's public URL + token
from env and sends the bearer header. All credentials/URLs live in env only.

**Why:** Cloud Run gives genuine public HTTPS URLs, scale-to-zero free tier, auto-TLS, and
dovetails with the Director's Google account and the step-8 Gmail API — the strongest
"cloud distributed deployment" artifact for the README. A static bearer token is the literal
reading of "tokens", is fully unit-testable offline, and keeps the cop/thief **asymmetry**
(distinct tokens). One image keeps the build simple; env-gated auth keeps the 152 existing
tests green.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Google Cloud Run, containerized | ✅ chosen | Real public HTTPS, free tier, auto-TLS, aligns with Google account + step 8 |
| Cloudflare/ngrok tunnel | ❌ rejected | Servers would still run on the operator's machine — weaker "deployed to cloud" story (kept as a documented fallback only) |
| Fly.io / Render | ❌ rejected | Yet another account; Cloud Run is the better Google-ecosystem fit |
| Per-server bearer token (env) | ✅ chosen | Literal "tokens"; offline-testable (401/200); preserves asymmetry |
| FastMCP JWT/OAuth | ❌ rejected | Heavier, harder to test offline, overkill for the grade |
| Platform-only auth (Cloud Run IAM) | ❌ rejected | No code artifact in the repo to show/grade |
| Two Dockerfiles | ❌ rejected | One image + `MCP_ROLE` is simpler and shares the build |
| URLs/tokens in config.yaml | ❌ rejected | Secrets in git violates cyber hygiene — env only |

## 5. Dependencies & interfaces
- **Consumes from prior steps:** `build_cop_server`/`build_thief_server` + their `__main__`
  (step 2); `HttpGateway`/`ServerGateway` protocol + `InMemoryGateway` (step 3); `load_config`
  and the trailing-optional `Config` pattern (step 2+); `config.servers.{cop,thief}.{host,port}`.
- **Exposes to later steps:** nothing structural for step 8 (Gmail is client-side); leaves a
  reusable **deployed-server + bearer-auth** pattern and a populated `.env` for the operator.
- **Touches config keys:** none required to be added with secrets. Optional non-secret
  `deploy:` block (region, service-name prefix, cloud default port) **may** be added as a
  trailing-optional field if the deploy script needs defaults — but URLs/tokens stay in env.

## 6. Binding constraints (from the assignment)
- **LLM/orchestrator stays in the client** — only the two MCP tool-servers go to the cloud.
- **No hard-coding / config-driven** — local host/port still come from `config.yaml`; cloud
  host/port come from the Cloud Run `PORT` contract; **secrets/URLs come from env, never code**.
- **Resizable grid preserved** — deployment changes transport/auth only, not game params.
- **Servers stay stateless validate-only** (step 2/3 invariant) — least-privilege by design.
- **Cyber hygiene** — TLS-only (Cloud Run), no secrets in git, non-root container, token never logged.

## 7. Key design decisions
- **Files/modules:**
  - `Dockerfile` (repo root) — uv install from `pyproject.toml`/`uv.lock`, non-root `USER`,
    `CMD` dispatches on `MCP_ROLE` to run cop or thief server.
  - `src/mcp_servers/cop_server.py` / `thief_server.py` — `__main__` reads `PORT`/host from
    env when present (bind `0.0.0.0:$PORT`), else config; wires the auth gate when the
    server's token env var is set.
  - `src/mcp_servers/auth.py` (new) — small helper that builds the bearer-token verifier /
    middleware from a token string, or returns "no auth" when the token is `None`.
  - `src/orchestrator/gateway.py` — `HttpGateway` learns optional `auth_token` + reads
    per-server public URL/token from env; sends `Authorization: Bearer`.
  - `deploy/deploy.sh` (or documented commands) + `docs/step7_cloud_deploy/DEPLOY.md` runbook.
  - `.env.example`, `.gitignore` (ensure `.env`, `runs/`), `.dockerignore`.
- **Env contract (single source of truth for deploy):**
  - Server side: `MCP_ROLE` (cop|thief), `PORT` (injected by Cloud Run), `COP_AUTH_TOKEN`,
    `THIEF_AUTH_TOKEN`.
  - Client side: `COP_SERVER_URL`, `THIEF_SERVER_URL`, `COP_AUTH_TOKEN`, `THIEF_AUTH_TOKEN`.
- **Auth semantics:** token unset ⇒ server open (local/in-memory tests + dev). Token set ⇒
  missing/incorrect bearer ⇒ 401; correct ⇒ normal tool response. Distinct token per server.
- **Key signatures (intent):**
  - `build_auth(token: str | None) -> <verifier/middleware or None>` — None ⇒ open server.
  - `HttpGateway(url: str, auth_token: str | None = None)` — header injection when token set.
  - `from_env()`-style helper on the gateway/orchestrator to assemble both gateways from env.

## 8. Acceptance criteria (how we know the step is done)
1. A single `Dockerfile` builds an image that runs the cop server with `MCP_ROLE=cop` and the
   thief server with `MCP_ROLE=thief`, binding `0.0.0.0:$PORT`.
2. With `*_AUTH_TOKEN` set, a request with no token or a wrong token is rejected (401); a
   request with the correct token succeeds — proven by an offline test for each server.
3. With the token env unset, both servers and the existing in-memory tests run unchanged
   (the prior 152 tests still pass; no token required locally).
4. `HttpGateway` sends the `Authorization: Bearer` header when given a token and targets the
   env-provided public URL; falls back to the config localhost URL with no header when unset —
   covered by a test.
5. No secret (token, URL) appears anywhere in the repo: `config.yaml`, `src/`, or git history;
   `.env` is git-ignored and `.env.example` documents the shape. Grep gate clean.
6. Container runs as a non-root user; deps are pinned via `uv.lock`; `.dockerignore` excludes
   `runs/`, `.env`, caches.
7. `docs/step7_cloud_deploy/DEPLOY.md` is a complete runbook: build → push → `gcloud run deploy`
   (both services) → set token env/secrets → capture the 2 public URLs → smoke-test with curl.
8. Ruff clean; every new `src/` file ≤150 lines; no hard-coded grid/port/model in new code.
9. **(Manual operator acceptance)** Both services are actually deployed to Cloud Run and the
   **two public HTTPS URLs** are recorded in the README, with a curl/`ping` showing 401 without
   the token and a valid response with it. Needs interactive `gcloud auth login`.

## 9. Resolved questions / open items
- **Q:** Real cloud vs tunnel? → **A:** Google Cloud Run (container). Tunnel kept only as a documented fallback in DEPLOY.md.
- **Q:** Auth mechanism? → **A:** Per-server static bearer token from env; distinct token per server; active only when env var set.
- **Q:** One image or two? → **A:** One image, role via `MCP_ROLE`.
- **Q:** Where do URLs/tokens live? → **A:** Env / `.env` only — never `config.yaml`, never git.
- **Q:** Does the live deploy happen in-session? → **A:** The *code + runbook + tests* are the in-repo deliverable; the actual `gcloud run deploy` + 2 URLs is a manual operator step at the end of the Developer session (interactive `gcloud auth login` required) and is captured for the README like the step-6 screenshot.
- **Still open (note for Builder):** the exact **FastMCP v3 bearer-auth API** and the **FastMCP Client bearer/header API** MUST be verified live before writing the TODO (see §10).

## 10. Notes for the Builder session
- **VERIFY LIVE before writing the TODO** (via context7 / FastMCP docs), and record it in a
  `SDK_REFERENCE_fastmcp_auth.md` like prior steps:
  1. How FastMCP v3 attaches a **static/bearer token verifier** to a server (e.g. an auth
     provider/verifier passed to `FastMCP(...)`, or middleware on the underlying ASGI/Starlette
     app via `mcp.http_app()`), and exactly what an unauthorized request returns (401).
  2. How the FastMCP **`Client`** sends a bearer token / custom headers to an HTTP server
     (e.g. an `auth=`/`headers=` argument) — `HttpGateway` needs this.
  3. The current uv Docker pattern (`uv sync --frozen`, non-root user) and how `mcp.run(transport="http", host="0.0.0.0", port=$PORT)` behaves under Cloud Run.
- **Put the most TODO detail** in: (a) `Dockerfile` (exact uv steps, `MCP_ROLE` dispatch,
  non-root `USER`, `$PORT`), (b) `auth.py` + the server `__main__` env-gated wiring, (c) the
  `HttpGateway` header/URL-from-env change with a backward-compatible default, and (d) the
  `DEPLOY.md` runbook with copy-paste `gcloud` commands.
- **Backward-compatibility is mandatory:** the 152 existing tests and local `python -m`
  run must keep working with **no token and no env** set. Auth and cloud-binding are strictly
  additive, env-triggered behavior.
- **Cyber-hygiene checklist** to encode as boxes: `.env.example`, `.gitignore` (.env, runs/),
  `.dockerignore`, non-root container, pinned `uv.lock`, token never logged, distinct tokens,
  TLS-only note, least-privilege (servers remain stateless validate-only).
- **Segal gate** still binds: ruff clean, ≤150 lines/file, ≥85% coverage on new testable code,
  no hard-coded values, no secrets, uv-only.
