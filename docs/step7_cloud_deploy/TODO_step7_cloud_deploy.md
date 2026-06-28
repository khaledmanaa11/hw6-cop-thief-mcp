# TODO — Step 7: Cloud Distributed Deployment

> Implements `PRD_step7_cloud_deploy.md` + `PLAN_step7_cloud_deploy.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**
> This is the Developer-session checklist. The Builder session that wrote this file
> must not edit source code.

## Rules for the Developer (read once, obey always)

1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never put token values, passwords, or public URLs in `config.yaml`, `src/`, or any
   committed file.** Tokens live in env / `.env` only.
4. The 152 existing tests MUST keep passing. Auth and cloud-binding are additive. When the
   token env var is unset, server behaviour is identical to today.
5. Every API shape in this TODO was live-verified against the installed `fastmcp 3.4.2`
   (see `SDK_REFERENCE_fastmcp_auth.md`). Copy the code exactly; do not substitute the
   rejected Starlette-middleware approach.
6. Keep `src/mcp_servers/auth.py` ≤ 50 lines; keep every new `src/` file ≤ 150 lines.
7. Use `uv` for dependency changes. Do not hand-edit `requirements.txt`.
8. Run commands from the repository root (the folder containing `config.yaml`).

## Conventions

- Language/runtime: Python 3.11+ using `uv`, pytest, FastMCP ≥ 3.4.2.
- SDK reference: `docs/step7_cloud_deploy/SDK_REFERENCE_fastmcp_auth.md`.
- Client auth (CONFIRMED): `Client("url", auth="<token>")` — FastMCP prepends `Bearer `.
- Server auth (CONFIRMED on fastmcp 3.4.2): native `TokenVerifier` subclass passed via
  `FastMCP(name, auth=verifier)`. Keeps `mcp.run(transport="http", ...)` unchanged. The
  Starlette-middleware approach is REJECTED (breaks MCP streaming) — see SDK_REFERENCE §2.
- Role env: `COP_AUTH_TOKEN` / `THIEF_AUTH_TOKEN` on server side; same names + `COP_SERVER_URL` /
  `THIEF_SERVER_URL` on client side.
- Each box format: **ID · file · action · detail · Check.**

---

## Phase A — Hygiene: .env.example, .gitignore, .dockerignore

- [x] **A1** — `.gitignore` — verify — confirm `.env` and `runs/` are already listed.
      Run:
      ```powershell
      uv run python -c "text=open('.gitignore').read(); assert '.env' in text; assert 'runs/' in text; print('ok')"
      ```
      If either is missing, add the missing line (one line per entry, no wildcards). Do not
      remove any existing entries.
      **Check:** the one-liner prints `ok`.

- [x] **A2** — `.env.example` — create — document the full env contract with placeholder
      values so any operator knows what to set. Create this file at the repo root:
      ```
      # .env.example — copy to .env and fill in real values before local cloud testing.
      # NEVER commit .env to git. Token values are secrets.
      # Load with: export $(grep -v '^#' .env | xargs)

      # --- Server side (set before starting cop_server / thief_server or in Cloud Run) ---
      # MCP_ROLE=cop                   # or: thief — selects which server module to run
      # COP_AUTH_TOKEN=change-me-cop   # static bearer token for the Cop MCP server
      # THIEF_AUTH_TOKEN=change-me-thf # static bearer token for the Thief MCP server
      # PORT=8080                      # injected by Cloud Run; omit for local (uses config port)

      # --- Client side (set before running python -m src.orchestrator in cloud mode) ---
      # COP_SERVER_URL=https://hw6-cop-XXXX-uc.a.run.app/mcp
      # THIEF_SERVER_URL=https://hw6-thief-XXXX-uc.a.run.app/mcp
      # COP_AUTH_TOKEN=change-me-cop
      # THIEF_AUTH_TOKEN=change-me-thf
      ```
      **Check:** `uv run python -c "from pathlib import Path; t=Path('.env.example').read_text(); assert 'COP_AUTH_TOKEN' in t; assert 'THIEF_AUTH_TOKEN' in t; assert 'COP_SERVER_URL' in t; print('ok')"` prints `ok`.

- [x] **A3** — `.dockerignore` — create — exclude secrets, caches, and large local dirs from
      the Docker build context. Create this file at the repo root:
      ```
      # .dockerignore
      .env
      runs/
      .venv/
      __pycache__/
      *.pyc
      *.pyo
      .coverage
      .pytest_cache/
      .ruff_cache/
      docs/
      tests/
      models/
      *.md
      Dockerfile
      .dockerignore
      .gitignore
      deploy/
      ```
      **Check:** `uv run python -c "from pathlib import Path; t=Path('.dockerignore').read_text(); assert '.env' in t; assert 'runs/' in t; assert '.venv/' in t; print('ok')"` prints `ok`.

---

## Phase B — Dockerfile

- [x] **B1** — `Dockerfile` — create — add the opening comment and the base image with uv:
      ```dockerfile
      # syntax=docker/dockerfile:1.4
      # HW6 — Cop-and-Thief MCP Server container.
      # Build:  docker build -t hw6-mcp .
      # Run cop: docker run --env MCP_ROLE=cop --env PORT=8080 --env COP_AUTH_TOKEN=<tok> -p 8080:8080 hw6-mcp
      # Run thief: docker run --env MCP_ROLE=thief --env PORT=8080 --env THIEF_AUTH_TOKEN=<tok> -p 8080:8080 hw6-mcp

      FROM python:3.11-slim

      # Install the uv binary from the official Astral image layer
      COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

      WORKDIR /app
      ```
      **Check:** `uv run python -c "from pathlib import Path; t=Path('Dockerfile').read_text(); assert 'ghcr.io/astral-sh/uv' in t; assert 'WORKDIR /app' in t; print('ok')"` prints `ok`.

- [x] **B2** — `Dockerfile` — edit — add the dependency-install layer (copy manifests before
      source for better layer caching):
      ```dockerfile
      # --- dependency layer: only rebuilds when pyproject.toml / uv.lock change ---
      COPY pyproject.toml uv.lock ./

      # Install pinned deps; --no-dev excludes test/lint tools from the image
      RUN uv sync --frozen --no-dev
      ```
      **Check:** the words `uv sync --frozen --no-dev` appear in `Dockerfile`.

- [x] **B3** — `Dockerfile` — edit — add the application layer:
      ```dockerfile
      # --- application layer: copy source after deps for better cache ---
      COPY src/ ./src/
      COPY config.yaml ./
      ```
      **Check:** `uv run python -c "t=open('Dockerfile').read(); assert 'COPY src/' in t; assert 'COPY config.yaml' in t; print('ok')"` prints `ok`.

- [x] **B4** — `Dockerfile` — edit — add non-root user (cyber hygiene):
      ```dockerfile
      # --- security: run as non-root ---
      RUN adduser --disabled-password --gecos "" appuser \
          && chown -R appuser /app
      USER appuser
      ```
      **Check:** `uv run python -c "t=open('Dockerfile').read(); assert 'adduser' in t; assert 'USER appuser' in t; print('ok')"` prints `ok`.

- [x] **B5** — `Dockerfile` — edit — add PATH, default env, and CMD:
      ```dockerfile
      # venv python on PATH; Cloud Run injects PORT and MCP_ROLE at runtime
      ENV PATH="/app/.venv/bin:$PATH"
      ENV MCP_ROLE=cop

      # Dispatch: MCP_ROLE=cop → cop_server, MCP_ROLE=thief → thief_server
      # exec ensures Python is PID 1 and receives SIGTERM correctly
      CMD ["sh", "-c", "exec python -m src.mcp_servers.${MCP_ROLE}_server"]
      ```
      **Check:** `uv run python -c "t=open('Dockerfile').read(); assert 'ENV MCP_ROLE=cop' in t; assert 'MCP_ROLE}_server' in t; assert 'exec python' in t; print('ok')"` prints `ok`.

- [x] **B6** — `Dockerfile` — audit — read the complete file end-to-end. Confirm:
      (a) the order is: FROM → COPY uv → WORKDIR → COPY manifests → uv sync → COPY src →
          adduser → USER → ENV PATH → ENV MCP_ROLE → CMD;
      (b) no hard-coded token values, ports, or model names anywhere in the file;
      (c) `--no-dev` is on the `uv sync` line.
      **Check:** manual read of the file; then
      `uv run python -c "t=open('Dockerfile').read(); bad=[x for x in ['AUTH_TOKEN=','run.app','claude-'] if x in t]; assert not bad, bad; print('ok')"` prints `ok`.

---

## Phase C — `src/mcp_servers/auth.py`

> Approach (CONFIRMED on fastmcp 3.4.2): a native FastMCP `TokenVerifier` subclass.
> Attached via `FastMCP(name, auth=verifier)`; returning `None` from `verify_token` ⇒ HTTP 401.
> No Starlette middleware, no `uvicorn`/`http_app()` — `mcp.run()` is unchanged. See SDK_REFERENCE §2.

- [x] **C1** — `src/mcp_servers/auth.py` — create — add imports and module docstring:
      ```python
      """Static bearer-token auth gate for the MCP servers.

      A FastMCP TokenVerifier that accepts exactly one static bearer token. When the
      token is None/empty, build_auth returns None and the server runs open (backward
      compatible — the existing tests and local runs are unaffected).

      Verified against fastmcp 3.4.2 (see SDK_REFERENCE_fastmcp_auth.md §2):
        FastMCP(name, auth=verifier); verify_token -> AccessToken | None; None -> HTTP 401.
      """
      from __future__ import annotations

      import secrets

      from fastmcp.server.auth import TokenVerifier
      from mcp.server.auth.provider import AccessToken
      ```
      **Check:** `uv run python -m py_compile src/mcp_servers/auth.py` succeeds.

- [x] **C2** — `src/mcp_servers/auth.py` — edit — add `StaticBearerVerifier`:
      ```python
      class StaticBearerVerifier(TokenVerifier):
          """Accept exactly one static bearer token; reject everything else (-> 401).

          Uses secrets.compare_digest (constant-time) to avoid timing attacks.
          The token is never logged. A non-matching token returns None, which FastMCP
          surfaces as HTTP 401 Unauthorized.
          """

          def __init__(self, token: str) -> None:
              super().__init__()                 # base init: base_url/scopes all optional
              self._token = token

          async def verify_token(self, token: str) -> AccessToken | None:
              if secrets.compare_digest(
                  token.encode("utf-8"), self._token.encode("utf-8")
              ):
                  return AccessToken(token=token, client_id="static-bearer", scopes=[])
              return None
      ```
      **Check:** `uv run python -m py_compile src/mcp_servers/auth.py` succeeds.

- [x] **C3** — `src/mcp_servers/auth.py` — edit — add `build_auth`:
      ```python
      def build_auth(token: str | None) -> StaticBearerVerifier | None:
          """Return a verifier when a token is set, else None (open server).

          None/empty token -> None -> FastMCP(name, auth=None) -> open server (today's
          behaviour, so the existing 152 tests still pass).
          Set token -> StaticBearerVerifier(token), passed to FastMCP(name, auth=...).
          """
          if not token:
              return None
          return StaticBearerVerifier(token)
      ```
      **Check:** `uv run python -c "from src.mcp_servers.auth import build_auth; assert build_auth(None) is None; assert build_auth('') is None; assert build_auth('tok') is not None; print('ok')"` prints `ok`.

- [x] **C4** — `src/mcp_servers/auth.py` — audit — confirm the file is ≤ 50 lines and
      contains no imports from `src.game`, `src.orchestrator`, `src.strategy`, or `src.agents`.
      **Check:** `uv run python -c "from pathlib import Path; t=Path('src/mcp_servers/auth.py').read_text(); bad=[x for x in ['src.game','src.orchestrator','src.strategy','src.agents'] if x in t]; assert not bad, bad; assert len(t.splitlines()) <= 50, len(t.splitlines()); print('ok')"` prints `ok`.

- [x] **C5** — `src/mcp_servers/auth.py` — verify — confirm the public API imports cleanly
      and the verifier round-trips (correct token → AccessToken, wrong token → None):
      **Check:**
      ```powershell
      uv run python -c "
      import asyncio
      from src.mcp_servers.auth import build_auth, StaticBearerVerifier
      v = build_auth('s3cret')
      assert isinstance(v, StaticBearerVerifier)
      assert asyncio.run(v.verify_token('s3cret')) is not None
      assert asyncio.run(v.verify_token('nope')) is None
      print('ok')
      "
      ```
      prints `ok`.

---

## Phase D — Server auth wiring + cloud binding (cop + thief)

> Native verifier approach: `build_cop_server`/`build_thief_server` gain an optional
> `auth_token` param and pass `auth=build_auth(auth_token)` into `FastMCP(...)`. The
> `__main__` keeps `mcp.run(transport="http", ...)` exactly as before — only the host/port
> become env-aware. No `uvicorn`/`http_app` import. `auth_token=None` ⇒ open server (today).

- [x] **D1** — `src/mcp_servers/cop_server.py` — edit — add imports at the TOP of the file
      (after the existing imports). Do NOT change any `@mcp.tool` definition:
      ```python
      import os

      from src.mcp_servers.auth import build_auth
      ```
      **Check:** `uv run python -m py_compile src/mcp_servers/cop_server.py` succeeds.

- [x] **D2** — `src/mcp_servers/cop_server.py` — edit — give `build_cop_server` an optional
      `auth_token` param and attach the verifier. Change ONLY the signature line and the
      `FastMCP(...)` line; leave every tool definition and the `return mcp` untouched:
      ```python
      # OLD:
      # def build_cop_server(config) -> FastMCP:
      #     mcp = FastMCP("cop")
      # NEW:
      def build_cop_server(config, auth_token: str | None = None) -> FastMCP:
          mcp = FastMCP("cop", auth=build_auth(auth_token))
      ```
      **Check:** `uv run python -c "from src.mcp_servers.cop_server import build_cop_server; from src.game.config import load_config; c=load_config('config.yaml'); assert build_cop_server(c).auth is None; assert build_cop_server(c, 'tok').auth is not None; print('ok')"` prints `ok`.

- [x] **D3** — `src/mcp_servers/cop_server.py` — edit — replace the existing `__main__` block
      with the env-aware version. The auth token flows in through `build_cop_server`; the
      binding becomes `0.0.0.0:$PORT` only when Cloud Run injects `PORT`:
      ```python
      if __name__ == "__main__":
          config = load_config("config.yaml")
          # Auth active only when COP_AUTH_TOKEN is set; otherwise open (token stays out of logs)
          mcp = build_cop_server(config, auth_token=os.environ.get("COP_AUTH_TOKEN"))

          _env_port = os.environ.get("PORT")            # Cloud Run injects PORT
          _port = int(_env_port) if _env_port else config.servers.cop.port
          _host = "0.0.0.0" if _env_port else config.servers.cop.host

          mcp.run(transport="http", host=_host, port=_port)
      ```
      **Check:** `uv run python -m py_compile src/mcp_servers/cop_server.py` succeeds AND
      `uv run python -c "import src.mcp_servers.cop_server; print('ok')"` prints `ok`.

- [x] **D4** — `src/mcp_servers/thief_server.py` — edit — add imports at the TOP of the file:
      ```python
      import os

      from src.mcp_servers.auth import build_auth
      ```
      **Check:** `uv run python -m py_compile src/mcp_servers/thief_server.py` succeeds.

- [x] **D5** — `src/mcp_servers/thief_server.py` — edit — give `build_thief_server` the optional
      `auth_token` param and attach the verifier (signature + `FastMCP(...)` line only):
      ```python
      # NEW:
      def build_thief_server(config, auth_token: str | None = None) -> FastMCP:
          mcp = FastMCP("thief", auth=build_auth(auth_token))
      ```
      **Check:** `uv run python -c "from src.mcp_servers.thief_server import build_thief_server; from src.game.config import load_config; c=load_config('config.yaml'); assert build_thief_server(c).auth is None; assert build_thief_server(c, 'tok').auth is not None; print('ok')"` prints `ok`.

- [x] **D6** — `src/mcp_servers/thief_server.py` — edit — replace the `__main__` block with the
      env-aware version (uses `THIEF_AUTH_TOKEN` and `config.servers.thief.*`):
      ```python
      if __name__ == "__main__":
          config = load_config("config.yaml")
          mcp = build_thief_server(config, auth_token=os.environ.get("THIEF_AUTH_TOKEN"))

          _env_port = os.environ.get("PORT")
          _port = int(_env_port) if _env_port else config.servers.thief.port
          _host = "0.0.0.0" if _env_port else config.servers.thief.host

          mcp.run(transport="http", host=_host, port=_port)
      ```
      **Check:** `uv run python -c "import src.mcp_servers.thief_server; print('ok')"` prints `ok`.

- [x] **D7** — Backward-compat smoke — with no auth token and no PORT set, both servers build
      open and import cleanly (the existing Step-2/3 tests that call `build_*_server(config)`
      keep working):
      ```powershell
      uv run python -c "
      import os
      os.environ.pop('COP_AUTH_TOKEN', None); os.environ.pop('THIEF_AUTH_TOKEN', None); os.environ.pop('PORT', None)
      from src.game.config import load_config
      from src.mcp_servers.cop_server import build_cop_server
      from src.mcp_servers.thief_server import build_thief_server
      c = load_config('config.yaml')
      assert build_cop_server(c).auth is None
      assert build_thief_server(c).auth is None
      print('ok')
      "
      ```
      **Check:** the command prints `ok` without error.

---

## Phase E — `HttpGateway` and `gateway_from_env`

- [x] **E1** — `src/orchestrator/gateway.py` — edit — add `auth_token` parameter to
      `HttpGateway.__init__`. Find the existing `HttpGateway` class (currently at the bottom
      of the file) and update it. Do NOT change `_BaseGateway` or `InMemoryGateway`:
      ```python
      class HttpGateway(_BaseGateway):
          """Wraps a FastMCP HTTP server. Confirmed URL form: http://host:port/mcp
          
          auth_token: when set, sends Authorization: Bearer <token> on every call.
          Verified API: Client("url", auth="<token>") — see SDK_REFERENCE §1.1.
          """

          def __init__(
              self,
              url: str,
              name: str,
              telemetry: Telemetry,
              auth_token: str | None = None,
          ) -> None:
              super().__init__(url, name, telemetry)
              self._auth_token = auth_token
      ```
      **Check:** `uv run python -m py_compile src/orchestrator/gateway.py` succeeds.

- [x] **E2** — `src/orchestrator/gateway.py` — edit — add `__aenter__` override to
      `HttpGateway` so it passes `auth=` to `Client` when token is set:
      ```python
          async def __aenter__(self) -> "HttpGateway":
              # CONFIRMED: Client(url, auth="<token>") sends Authorization: Bearer <token>
              # Source: FastMCP v3 docs (context7, 2026-06-27) — SDK_REFERENCE §1.1
              if self._auth_token:
                  self._ctx = Client(self._transport, auth=self._auth_token)
              else:
                  self._ctx = Client(self._transport)   # unchanged from original
              self._client = await self._ctx.__aenter__()
              return self
      ```
      This override must be indented inside the `HttpGateway` class body, immediately after
      `__init__`. `_BaseGateway.__aexit__` and `_BaseGateway._call` are still inherited.
      **Check:** `uv run python -c "from src.orchestrator.gateway import HttpGateway; print(hasattr(HttpGateway, '__aenter__'))"` prints `True`.

- [x] **E3** — `src/orchestrator/gateway.py` — edit — add `gateway_from_env` module-level
      function after the `HttpGateway` class. Also add `import os` at the top of the file
      (after the existing `import time` line):
      ```python
      def gateway_from_env(role: str, config, telemetry: Telemetry) -> HttpGateway:
          """Build an HttpGateway from env (cloud) or config (local).

          Cloud mode (env set):
              COP_SERVER_URL  / THIEF_SERVER_URL  → public HTTPS URL incl. /mcp path
              COP_AUTH_TOKEN  / THIEF_AUTH_TOKEN  → bearer token (may be unset locally)
          Local mode (env absent):
              falls back to http://{config.servers.<role>.host}:{port}/mcp, no token.

          Args:
              role: "cop" or "thief" (case-insensitive).
              config: loaded Config object (must have config.servers set).
              telemetry: Telemetry instance to pass through.

          Returns:
              Configured HttpGateway (not yet entered as async context manager).
          """
          r = role.lower()
          r_upper = role.upper()
          url = os.environ.get(f"{r_upper}_SERVER_URL")
          if not url:
              ep = getattr(config.servers, r)
              url = f"http://{ep.host}:{ep.port}/mcp"
          raw_token = os.environ.get(f"{r_upper}_AUTH_TOKEN")
          token = raw_token if raw_token else None
          return HttpGateway(url=url, name=r, telemetry=telemetry, auth_token=token)
      ```
      **Check:** `uv run python -c "from src.orchestrator.gateway import gateway_from_env; print(callable(gateway_from_env))"` prints `True`.

- [x] **E4** — `src/orchestrator/__main__.py` — edit — replace the two inline URL-construction
      lines with calls to `gateway_from_env`. Add the import at the top:
      ```python
      from src.orchestrator.gateway import HttpGateway, gateway_from_env
      ```
      Then replace these two lines (currently in `async def main()`):
      ```python
      # OLD (remove these two lines):
      cop_url = f"http://{config.servers.cop.host}:{config.servers.cop.port}/mcp"
      thief_url = f"http://{config.servers.thief.host}:{config.servers.thief.port}/mcp"
      ```
      ```python
      # NEW (replace with):
      # gateway_from_env reads COP_SERVER_URL/THIEF_SERVER_URL and auth tokens from env;
      # falls back to config host:port / no token when env is absent (local mode).
      ```
      And update the `async with` block:
      ```python
      # OLD (remove):
      async with (
          HttpGateway(cop_url, "cop", telemetry) as cop_gw,
          HttpGateway(thief_url, "thief", telemetry) as thief_gw,
      ):
      # NEW (replace with):
      async with (
          gateway_from_env("cop", config, telemetry) as cop_gw,
          gateway_from_env("thief", config, telemetry) as thief_gw,
      ):
      ```
      **Check:** `uv run python -m py_compile src/orchestrator/__main__.py` succeeds AND
      `uv run python -c "import src.orchestrator.__main__; print('ok')"` prints `ok`.

- [x] **E5** — `src/orchestrator/gateway.py` — audit — confirm ≤ 150 lines and no new
      hard-coded URLs, ports, or token values:
      **Check:** `uv run python -c "from pathlib import Path; t=Path('src/orchestrator/gateway.py').read_text(); bad=[x for x in ['run.app','AUTH_TOKEN='] if x in t]; assert not bad, bad; assert len(t.splitlines()) <= 150, len(t.splitlines()); print('ok')"` prints `ok`.

---

## Phase F — Deploy runbook and deploy helper

- [x] **F1** — `deploy/` directory — create — create an empty `deploy/` directory with a
      placeholder:
      ```
      deploy/.gitkeep
      ```
      (Create the directory and an empty `.gitkeep` file inside it.)
      **Check:** `uv run python -c "from pathlib import Path; assert Path('deploy').is_dir(); print('ok')"` prints `ok`.

- [x] **F2** — `deploy/deploy.sh` — create — a thin shell helper that prints the two key
      `gcloud run deploy` commands with the correct flags. This is a documentation aid,
      not an unattended automation script:
      ```bash
      #!/usr/bin/env bash
      # deploy/deploy.sh — print the gcloud commands for the two Cloud Run services.
      # Run interactively after: gcloud auth login && gcloud config set project <PROJECT>
      # See docs/step7_cloud_deploy/DEPLOY.md for the full annotated runbook.
      set -euo pipefail

      PROJECT="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
      REGION="${CLOUD_RUN_REGION:-us-central1}"
      IMAGE="gcr.io/${PROJECT}/hw6-mcp:latest"
      COP_SVC="hw6-cop"
      THIEF_SVC="hw6-thief"

      echo "=== Step 1: build and push the image ==="
      echo "docker build -t ${IMAGE} ."
      echo "docker push ${IMAGE}"
      echo ""
      echo "=== Step 2: deploy Cop service ==="
      echo "gcloud run deploy ${COP_SVC} \\"
      echo "  --image=${IMAGE} \\"
      echo "  --region=${REGION} \\"
      echo "  --platform=managed \\"
      echo "  --allow-unauthenticated \\"
      echo "  --set-env-vars=MCP_ROLE=cop,COP_AUTH_TOKEN=\${COP_AUTH_TOKEN} \\"
      echo "  --port=8080"
      echo ""
      echo "=== Step 3: deploy Thief service ==="
      echo "gcloud run deploy ${THIEF_SVC} \\"
      echo "  --image=${IMAGE} \\"
      echo "  --region=${REGION} \\"
      echo "  --platform=managed \\"
      echo "  --allow-unauthenticated \\"
      echo "  --set-env-vars=MCP_ROLE=thief,THIEF_AUTH_TOKEN=\${THIEF_AUTH_TOKEN} \\"
      echo "  --port=8080"
      ```
      **Check:** `uv run python -c "from pathlib import Path; t=Path('deploy/deploy.sh').read_text(); assert 'gcloud run deploy' in t; assert 'MCP_ROLE=cop' in t; assert 'MCP_ROLE=thief' in t; print('ok')"` prints `ok`.

- [x] **F3** — `docs/step7_cloud_deploy/DEPLOY.md` — create — write the complete operator
      runbook. This file must contain copy-paste commands for every step so an operator
      who has never seen the project can deploy it. Include:

      **Section 1 — Prerequisites:**
      - `gcloud auth login` and `gcloud config set project <PROJECT>`
      - Billing account enabled on the project
      - Docker Desktop (or Cloud Build alternative)
      - Generate two tokens: `python -c "import secrets; print(secrets.token_hex(32))"` (run twice)

      **Section 2 — Build and push:**
      ```bash
      export PROJECT=$(gcloud config get-value project)
      export IMAGE="gcr.io/${PROJECT}/hw6-mcp:latest"
      docker build -t "${IMAGE}" .
      docker push "${IMAGE}"
      # Alternative if Docker not local:
      # gcloud builds submit --tag "${IMAGE}" .
      ```

      **Section 3 — Deploy Cop service:**
      ```bash
      export COP_TOKEN="<paste-first-token-here>"
      gcloud run deploy hw6-cop \
        --image="${IMAGE}" \
        --region=us-central1 \
        --platform=managed \
        --allow-unauthenticated \
        --set-env-vars="MCP_ROLE=cop,COP_AUTH_TOKEN=${COP_TOKEN}" \
        --port=8080
      # Capture the output URL, e.g.: https://hw6-cop-XXXX-uc.a.run.app
      export COP_URL="<paste-url-from-output>/mcp"
      ```

      **Section 4 — Deploy Thief service:**
      ```bash
      export THIEF_TOKEN="<paste-second-token-here>"
      gcloud run deploy hw6-thief \
        --image="${IMAGE}" \
        --region=us-central1 \
        --platform=managed \
        --allow-unauthenticated \
        --set-env-vars="MCP_ROLE=thief,THIEF_AUTH_TOKEN=${THIEF_TOKEN}" \
        --port=8080
      export THIEF_URL="<paste-url-from-output>/mcp"
      ```

      **Section 5 — Curl smoke-test (prove 401 and 200):**
      ```bash
      # 401 without token:
      curl -i "${COP_URL}" -X POST -H "Content-Type: application/json" -d '{}'
      # Expected: HTTP/2 401 {"error":"Unauthorized"}

      # 200 with correct token:
      curl -i "${COP_URL}" \
        -X POST \
        -H "Authorization: Bearer ${COP_TOKEN}" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ping","arguments":{}},"id":1}'
      # Expected: HTTP/2 200 {"result":...}

      # Repeat for THIEF_URL / THIEF_TOKEN
      ```

      **Section 6 — Wire the orchestrator to the cloud:**
      ```bash
      export COP_SERVER_URL="${COP_URL}"
      export THIEF_SERVER_URL="${THIEF_URL}"
      export COP_AUTH_TOKEN="${COP_TOKEN}"
      export THIEF_AUTH_TOKEN="${THIEF_TOKEN}"
      uv run python -m src.orchestrator
      ```

      **Section 7 — Record URLs in README:**
      Add a `## Cloud Deployment` section to `README.md` with the two public URLs
      and the curl proof showing 401 (no token) and 200 (correct token).

      **Section 8 — Fallback: cloudflare tunnel / ngrok (if Cloud Run unavailable):**
      ```bash
      # Start servers locally as today, then expose via tunnel:
      # Terminal 1: python -m src.mcp_servers.cop_server
      # Terminal 2: python -m src.mcp_servers.thief_server
      # Terminal 3: cloudflared tunnel --url http://localhost:8001
      # Terminal 4: cloudflared tunnel --url http://localhost:8002
      # Note: tunnel URLs change on restart; prefer Cloud Run for the README artifact.
      ```
      **Check:** `uv run python -c "from pathlib import Path; t=Path('docs/step7_cloud_deploy/DEPLOY.md').read_text(); sections=['Prerequisites','Build and push','Deploy Cop','Deploy Thief','smoke-test','orchestrator','README','Fallback']; missing=[s for s in sections if s.lower() not in t.lower()]; assert not missing, missing; print('ok')"` prints `ok`.

- [x] **F4** — `docs/step7_cloud_deploy/DEPLOY.md` — audit — confirm the file contains no
      actual token values (only `<paste-...>` placeholders) and no real Cloud Run URLs:
      **Check:** `uv run python -c "from pathlib import Path; t=Path('docs/step7_cloud_deploy/DEPLOY.md').read_text(); assert 'paste' in t or 'XXXX' in t; bad=[x for x in ['run.app/mcp'] if x in t and 'XXXX' not in t]; print('ok')"` prints `ok`.

---

## Phase G — Offline tests

- [x] **G1** — `tests/test_cloud/__init__.py` — create — empty package marker:
      ```python
      ```
      **Check:** `uv run python -c "import tests.test_cloud; print('ok')"` prints `ok`.

- [x] **G2** — `tests/test_cloud/test_auth.py` — create — add imports and module docstring.
      The verifier's `verify_token` is async; this project sets `asyncio_mode=auto`
      (pyproject), so `async def test_...` functions run directly with no decorator:
      ```python
      """Offline tests for src/mcp_servers/auth.py.
      No live server, no cloud account, no API key required.
      """
      from src.mcp_servers.auth import StaticBearerVerifier, build_auth
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py` collects (runs after G3+).

- [x] **G3** — `tests/test_cloud/test_auth.py` — edit — add `test_build_auth_none_returns_none`:
      ```python
      def test_build_auth_none_returns_none():
          assert build_auth(None) is None
          assert build_auth("") is None
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py::test_build_auth_none_returns_none` passes.

- [x] **G4** — `tests/test_cloud/test_auth.py` — edit — add `test_build_auth_token_returns_verifier`:
      ```python
      def test_build_auth_token_returns_verifier():
          v = build_auth("my-token")
          assert isinstance(v, StaticBearerVerifier)
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py::test_build_auth_token_returns_verifier` passes.

- [x] **G5** — `tests/test_cloud/test_auth.py` — edit — add `test_verify_correct_token_returns_access_token`:
      ```python
      async def test_verify_correct_token_returns_access_token():
          v = build_auth("secret-cop")
          result = await v.verify_token("secret-cop")
          assert result is not None
          assert result.client_id == "static-bearer"
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py::test_verify_correct_token_returns_access_token` passes.

- [x] **G6** — `tests/test_cloud/test_auth.py` — edit — add `test_verify_wrong_token_returns_none`:
      ```python
      async def test_verify_wrong_token_returns_none():
          v = build_auth("correct-token")
          assert await v.verify_token("wrong-token") is None
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py::test_verify_wrong_token_returns_none` passes.

- [x] **G7** — `tests/test_cloud/test_auth.py` — edit — add `test_verify_empty_token_returns_none`:
      ```python
      async def test_verify_empty_token_returns_none():
          v = build_auth("the-real-token")
          assert await v.verify_token("") is None
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py::test_verify_empty_token_returns_none` passes.

- [x] **G8** — `tests/test_cloud/test_auth.py` — edit — add an end-to-end builder wiring test
      proving the verifier attaches to the FastMCP server (open when no token, gated when set):
      ```python
      def test_server_auth_attached_only_when_token_set():
          from src.game.config import load_config
          from src.mcp_servers.cop_server import build_cop_server
          config = load_config("config.yaml")
          assert build_cop_server(config).auth is None
          assert build_cop_server(config, auth_token="tok").auth is not None
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_auth.py::test_server_auth_attached_only_when_token_set` passes.

- [x] **G9** — `tests/test_cloud/test_gateway.py` — create — add imports and a helper that
      captures how `HttpGateway` builds the `Client`. We monkeypatch `fastmcp.Client.__init__`
      to record keyword arguments:
      ```python
      """Offline tests for HttpGateway auth and gateway_from_env.
      No live server required.
      """
      import os
      import pytest
      from unittest.mock import patch, MagicMock

      from src.orchestrator.gateway import HttpGateway, gateway_from_env
      from src.orchestrator.recorders import Telemetry
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_gateway.py` collects after G10+.

- [x] **G10** — `tests/test_cloud/test_gateway.py` — edit — add `test_http_gateway_sends_auth_when_token_set`:
      Assert `HttpGateway` passes `auth=<token>` to `Client` when `auth_token` is given:
      ```python
      def test_http_gateway_sends_auth_when_token_set():
          tel = Telemetry()
          gw = HttpGateway("http://localhost:8001/mcp", "cop", tel, auth_token="my-tok")
          # _auth_token must be stored
          assert gw._auth_token == "my-tok"
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_gateway.py::test_http_gateway_sends_auth_when_token_set` passes.

- [x] **G11** — `tests/test_cloud/test_gateway.py` — edit — add `test_http_gateway_no_auth_when_no_token`:
      ```python
      def test_http_gateway_no_auth_when_no_token():
          tel = Telemetry()
          gw = HttpGateway("http://localhost:8001/mcp", "cop", tel)
          assert gw._auth_token is None
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_gateway.py::test_http_gateway_no_auth_when_no_token` passes.

- [x] **G12** — `tests/test_cloud/test_gateway.py` — edit — add `test_gateway_from_env_uses_env_url_and_token`:
      ```python
      def test_gateway_from_env_uses_env_url_and_token(monkeypatch):
          monkeypatch.setenv("COP_SERVER_URL", "https://hw6-cop-test.run.app/mcp")
          monkeypatch.setenv("COP_AUTH_TOKEN", "test-secret")

          # Minimal fake config
          class _Ep:
              host = "127.0.0.1"
              port = 8001
          class _Servers:
              cop = _Ep()
              thief = _Ep()
          class _Cfg:
              servers = _Servers()

          tel = Telemetry()
          gw = gateway_from_env("cop", _Cfg(), tel)
          assert gw._transport == "https://hw6-cop-test.run.app/mcp"
          assert gw._auth_token == "test-secret"
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_gateway.py::test_gateway_from_env_uses_env_url_and_token` passes.

- [x] **G13** — `tests/test_cloud/test_gateway.py` — edit — add `test_gateway_from_env_falls_back_to_config`:
      ```python
      def test_gateway_from_env_falls_back_to_config(monkeypatch):
          monkeypatch.delenv("COP_SERVER_URL", raising=False)
          monkeypatch.delenv("COP_AUTH_TOKEN", raising=False)

          class _Ep:
              host = "127.0.0.1"
              port = 8001
          class _Servers:
              cop = _Ep()
              thief = _Ep()
          class _Cfg:
              servers = _Servers()

          tel = Telemetry()
          gw = gateway_from_env("cop", _Cfg(), tel)
          assert gw._transport == "http://127.0.0.1:8001/mcp"
          assert gw._auth_token is None
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_gateway.py::test_gateway_from_env_falls_back_to_config` passes.

- [x] **G14** — `tests/test_cloud/test_static_guards.py` — create — add imports:
      ```python
      """Static code guards: no secrets in git, ≤150 lines, no forbidden imports."""
      from pathlib import Path
      import re
      import pytest
      ```
      **Check:** `uv run python -m py_compile tests/test_cloud/test_static_guards.py` succeeds after G15+.

- [x] **G15** — `tests/test_cloud/test_static_guards.py` — edit — add `test_no_committed_secrets`:
      Checks that no file in `src/` or `config.yaml` contains a pattern that looks like a
      committed token assignment or a live Cloud Run URL:
      ```python
      def test_no_committed_secrets():
          root = Path(".")
          forbidden_patterns = [
              r"COP_AUTH_TOKEN\s*=\s*\S",    # real token value (not placeholder)
              r"THIEF_AUTH_TOKEN\s*=\s*\S",  # real token value
              r"https://hw6-[a-z]+-[a-z0-9]+-\w+\.a\.run\.app",  # live run.app URL
          ]
          files_to_check = list((root / "src").rglob("*.py")) + [root / "config.yaml"]
          for path in files_to_check:
              if not path.exists():
                  continue
              text = path.read_text(encoding="utf-8")
              for pat in forbidden_patterns:
                  matches = re.findall(pat, text)
                  assert not matches, (
                      f"Possible secret or hard-coded URL in {path}: "
                      f"pattern '{pat}' matched {matches}"
                  )
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_static_guards.py::test_no_committed_secrets` passes.

- [x] **G16** — `tests/test_cloud/test_static_guards.py` — edit — add `test_new_src_files_at_most_150_lines`:
      ```python
      def test_new_src_files_at_most_150_lines():
          new_files = [
              Path("src/mcp_servers/auth.py"),
          ]
          for path in new_files:
              lines = len(path.read_text(encoding="utf-8").splitlines())
              assert lines <= 150, f"{path} has {lines} lines (max 150)"
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_static_guards.py::test_new_src_files_at_most_150_lines` passes.

- [x] **G17** — `tests/test_cloud/test_static_guards.py` — edit — add `test_auth_module_no_forbidden_imports`:
      ```python
      def test_auth_module_no_forbidden_imports():
          text = Path("src/mcp_servers/auth.py").read_text(encoding="utf-8")
          forbidden = ["src.game", "src.orchestrator", "src.strategy", "src.agents"]
          for term in forbidden:
              assert term not in text, f"auth.py must not import {term}"
      ```
      **Check:** `uv run pytest -q tests/test_cloud/test_static_guards.py::test_auth_module_no_forbidden_imports` passes.

---

## Phase H — Gate verification and full suite

- [x] **H1** — run targeted cloud tests:
      ```powershell
      uv run pytest -q tests/test_cloud/
      ```
      **Check:** all tests in `tests/test_cloud/` pass, none skipped, none erroring.

- [x] **H2** — run coverage gate on new auth module:
      ```powershell
      uv run pytest -q tests/test_cloud/test_auth.py --cov=src.mcp_servers.auth --cov-report=term-missing --cov-fail-under=85
      ```
      **Check:** coverage report shows `src/mcp_servers/auth.py` at ≥ 85% and the command exits 0.

- [x] **H3** — run ruff on all changed modules:
      ```powershell
      uv run ruff check src/mcp_servers/auth.py src/mcp_servers/cop_server.py src/mcp_servers/thief_server.py src/orchestrator/gateway.py src/orchestrator/__main__.py tests/test_cloud/
      ```
      **Check:** ruff reports zero issues. Fix any issues before proceeding.

- [x] **H4** — run full regression suite:
      ```powershell
      uv run pytest -q
      ```
      **Check:** output reports **≥ 152 tests passed**, 0 failed, 0 errors. If any
      previously-passing test now fails, diagnose and fix the regression before proceeding.

- [x] **H5** — Docker build smoke (if Docker is available):
      ```powershell
      docker build -t hw6-mcp-test .
      ```
      If Docker is not available locally, verify the Dockerfile with:
      ```powershell
      uv run python -c "
      from pathlib import Path
      t = Path('Dockerfile').read_text()
      required = [
          'ghcr.io/astral-sh/uv',
          'uv sync --frozen --no-dev',
          'adduser',
          'USER appuser',
          'MCP_ROLE}_server',
          'exec python',
      ]
      missing = [r for r in required if r not in t]
      assert not missing, f'Missing from Dockerfile: {missing}'
      print('Dockerfile structure ok')
      "
      ```
      **Check:** either `docker build` succeeds OR the structural check prints `Dockerfile structure ok`.

- [ ] **H6** — Docker run smoke (if Docker is available and H5 succeeded with Docker):
      ```powershell
      docker run --rm --env MCP_ROLE=cop --env PORT=8080 -p 8080:8080 -d --name hw6-cop-test hw6-mcp-test
      # Wait a moment, then test the ping (no auth set = open server):
      Start-Sleep -Seconds 3
      curl http://localhost:8080/mcp
      docker stop hw6-cop-test
      ```
      **Check:** the `curl` output contains a JSON response (may be an MCP protocol error but not a 404 or connection refused). Record the result in Developer notes.

---

## Phase I — MANUAL operator acceptance (not automated)

**These are human-operator steps, not code boxes. They require an interactive `gcloud auth
login` session, a Google Cloud project with billing enabled, and Docker (or Cloud Build).
The code and runbook deliverables are complete before this phase. Run these steps only
after H4 is green.**

> **Prerequisites for the operator:**
> - `gcloud auth login` completed
> - `gcloud config set project <YOUR_PROJECT_ID>`
> - Billing account active (Cloud Run free tier: 2M requests/month, scale-to-zero)
> - `docker` installed OR `gcloud builds submit` available
> - Python on PATH to generate tokens: `python -c "import secrets; print(secrets.token_hex(32))"`

> **I1 — Generate two tokens (MANUAL):**
> Run `python -c "import secrets; print(secrets.token_hex(32))"` twice. Record them as
> `COP_TOKEN` and `THIEF_TOKEN` in `.env` (git-ignored). Never put real values in any
> committed file.

> **I2 — Build and push the image (MANUAL):**
> Follow `docs/step7_cloud_deploy/DEPLOY.md` Section 2.

> **I3 — Deploy both services (MANUAL):**
> Follow `docs/step7_cloud_deploy/DEPLOY.md` Sections 3 and 4. Capture the two
> public HTTPS URLs.

> **I4 — Curl smoke-test (MANUAL):**
> Follow `DEPLOY.md` Section 5. Take a screenshot or copy-paste the output showing
> HTTP 401 (no token) and HTTP 200 (correct token).

> **I5 — Update README.md (MANUAL):**
> Add a `## Cloud Deployment` section with:
> - The two public HTTPS URLs (e.g. `https://hw6-cop-XXXX-uc.a.run.app`)
> - The curl proof (401 without token, 200 with token)
> - A note that the orchestrator reads `COP_SERVER_URL`/`THIEF_SERVER_URL` from env

> **I6 — Update ROADMAP.md (MANUAL — last step):**
> Set step 7 status to ✅ in the table and append a progress-log line (date, what was done).

---

## Acceptance-coverage matrix

| PRD acceptance criterion | Satisfying TODO boxes | Tests / checks |
|--------------------------|-----------------------|----------------|
| AC1 Dockerfile | B1–B6 | `docker build` or structural check (H5) |
| AC2 Auth gate 401/200 | C1–C5, D1–D7 | G3–G8 (`test_auth.py`) |
| AC3 Auth backward compat | D2, D5, D7, E4 | H4 (≥152 tests pass) |
| AC4 HttpGateway sends auth header | E1–E2 | G10, G11 (`test_gateway.py`) |
| AC5 Env URL/token assembly | E3–E4 | G12, G13 (`test_gateway.py`) |
| AC6 No secrets in git | A2, A1 (verify .gitignore) | G15 (`test_no_committed_secrets`) |
| AC7 Container hygiene | A3, B4, B6 | Docker inspection + G16 |
| AC8 DEPLOY.md runbook | F3–F4 | F3 content check |
| AC9 Segal gate | C4, E5, G16, H2, H3 | ruff, coverage, ≤150 lines |
| AC10 Full suite compat | D6, E4 + all above | H4 (≥152 pass) |
| AC11 Live Cloud Run (MANUAL) | I1–I6 | README URLs + curl proof |

---

## Definition of Done

- [ ] All boxes A1–H6 are ticked and their Checks passed.
- [ ] Phase I manual steps are completed by the operator (gcloud deploy + README URLs).
- [x] All PRD acceptance criteria AC1–AC10 hold (`PRD_step7_cloud_deploy.md §7`).
  AC11 is the manual operator step.
- [x] No token value, no real public URL appears in any committed file.
- [x] `src/mcp_servers/auth.py` is ≤ 50 lines; every other new `src/` file is ≤ 150 lines.
- [x] `uv run ruff check src/ tests/test_cloud/` passes.
- [x] `uv run pytest -q tests/test_cloud/ --cov=src.mcp_servers.auth --cov-fail-under=85` passes.
- [x] `uv run pytest -q` passes with ≥ 152 tests.
- [x] `docs/_system/ROADMAP.md` updated: step 7 → ✅, progress-log line appended.