# PRD — Step 7: Cloud Distributed Deployment

- **Status:** triplet-built
- **Source:** `DECISION_step7_cloud_deploy.md`; SDK ground truth: `SDK_REFERENCE_fastmcp_auth.md`
- **Assignment references:** §13 Table 4 (step 7: "Push MCP servers to cloud with tokens /
  secure tunnels / cyber hygiene; publish 2 public URLs"); cross-cutting server/client split
  constraint (LLM stays in the client).

---

## 1. Problem & context

Steps 1–6 run the full Cop-and-Thief dual-agent system locally: both FastMCP servers
(`src/mcp_servers/cop_server.py`, `thief_server.py`) bind to `127.0.0.1:8001/8002` and the
orchestrator connects as a local HTTP client. The system works end-to-end, but the two
tool-servers are not yet "in the cloud" — a requirement of assignment §13 Table 4.

Step 7 makes the architecture genuinely distributed. Each MCP server is containerised,
deployed to **Google Cloud Run** (real public HTTPS URLs, auto-TLS, scale-to-zero), and
gated by its own **static bearer token** read from environment variables. The orchestrator,
LLM brain, and referee remain entirely client-side (the binding constraint: LLM lives in the
client). The result: the system's brain runs on the operator's machine and talks to two
independently-deployed, authenticated tool-servers over the public internet, satisfying
"tokens / secure tunnels / cyber hygiene" in one go.

---

## 2. Goal & success metric

After this step, the project has:
1. A single `Dockerfile` that builds one container image deployable as either the Cop or Thief
   server (role chosen by `MCP_ROLE` env var), binding `0.0.0.0:$PORT` for Cloud Run.
2. A per-server static bearer-token auth gate that returns 401 when the token is missing or
   wrong, and passes through when correct — active only when the token env var is set.
3. An `HttpGateway` upgrade that sends `Authorization: Bearer` when given a token and falls
   back gracefully when not.
4. A complete deploy runbook (`DEPLOY.md`) with copy-paste `gcloud run deploy` commands.
5. All 152 existing tests still passing; auth and cloud binding are strictly additive.

The manual acceptance criterion — two live Cloud Run URLs in the README with a curl
demonstrating 401-without-token and 200-with-token — is a **human-operator step** that
requires an interactive `gcloud auth login` session and is not automated.

---

## 3. Stories

- As the **orchestrator / HttpGateway**, I need to read the Cop and Thief public HTTPS URLs
  and their bearer tokens from environment variables so that I can reach the cloud-deployed
  servers without hard-coding anything in source.
- As the **cop_server / thief_server process**, I need to bind `0.0.0.0:$PORT` when Cloud Run
  injects `PORT` and fall back to the config `host:port` otherwise, so that both local runs
  and Cloud Run deployments work from the same container.
- As the **auth gate**, I need to reject requests with a missing or wrong bearer token with
  HTTP 401 and accept the correct token, but only when my token env var is set, so that local
  and in-memory test runs require no credentials.
- As the **grader / README reader**, I need two live HTTPS URLs and a curl smoke-test
  demonstrating 401-without-token and a valid tool response with the correct token, so that
  "tokens / cyber hygiene / cloud distributed deployment" is proven.
- As the **CI pipeline**, I need auth, binding, and gateway tests to run completely offline
  (no live server, no cloud account, no API key) so the gate stays green on every push.

---

## 4. Functional requirements

- **FR1 — Single Dockerfile.** A `Dockerfile` at the repo root builds one image. Setting
  `MCP_ROLE=cop` runs `cop_server`, setting `MCP_ROLE=thief` runs `thief_server`.
  `MCP_ROLE=cop` is the default.
- **FR2 — Cloud Run binding.** Each server `__main__` reads `PORT` from env; when set it
  binds `0.0.0.0:$PORT`. When unset it falls back to `config.servers.<role>.host` and
  `config.servers.<role>.port`. No hard-coded host or port in new code.
- **FR3 — Bearer-token auth gate.** When the server's token env var (`COP_AUTH_TOKEN` for
  the Cop server, `THIEF_AUTH_TOKEN` for the Thief server) is set, all requests without a
  matching `Authorization: Bearer <token>` header receive HTTP 401. When the env var is
  unset, the server runs open (no auth required).
- **FR4 — Auth module.** A new `src/mcp_servers/auth.py` exports `build_auth(token: str | None)`
  returning a configured auth gate object or `None`. `None` means open server.
- **FR5 — HttpGateway auth header.** `HttpGateway` accepts `auth_token: str | None = None`.
  When set it sends `Authorization: Bearer <token>` on every request. When unset it sends no
  auth header (existing behaviour).
- **FR6 — Env-driven gateway assembly.** A helper `gateway_from_env(role, config, telemetry)`
  (or equivalent logic in `__main__`) reads `COP_SERVER_URL`/`THIEF_SERVER_URL` and
  `COP_AUTH_TOKEN`/`THIEF_AUTH_TOKEN` from env; falls back to config localhost URL with no
  token when env vars are absent.
- **FR7 — Cyber-hygiene artifacts.** `.env.example` documents the env contract. `.gitignore`
  has `.env` and `runs/` (already present; verify). `.dockerignore` excludes `runs/`, `.env`,
  `__pycache__`, `.venv`, `.coverage`. Container image uses a non-root user. Tokens are never
  logged. `uv.lock` pins all dependencies.
- **FR8 — Deploy runbook.** `docs/step7_cloud_deploy/DEPLOY.md` is a complete runbook:
  build → push → `gcloud run deploy` (both services) → set token secrets/env → capture 2
  URLs → curl smoke-test showing 401 without token and 200 with. Includes a documented
  fallback using `cloudflared` / `ngrok` if Cloud Run is unavailable.
- **FR9 — Offline-testable auth/wiring tests.** New tests in `tests/test_cloud/` cover:
  401-without-token, 401-wrong-token, 200-correct-token, `build_auth(None)` returns None,
  `HttpGateway` sends correct header, `gateway_from_env` env-to-URL wiring, binding fallback
  (PORT set → `0.0.0.0:PORT`, PORT unset → config values). All tests run without any live
  server, cloud account, or API key.
- **FR10 — No secrets in git.** No token value, no public URL appears in `config.yaml`,
  `src/`, or any committed file. A grep gate test asserts this. `.env` remains git-ignored.

---

## 5. Non-functional requirements

- **NFR1 — Config-driven:** all host/port values come from `config.yaml`; public URLs and
  tokens come from environment variables only — never from `config.yaml` or source.
- **NFR2 — Resizable:** deployment changes transport/auth only, not game parameters. The
  resizable-grid invariant is untouched.
- **NFR3 — Backward compatibility (CRITICAL):** the 152 existing tests and local
  `python -m src.mcp_servers.cop_server` / orchestrator runs must keep working with no token
  and no env set. Auth and cloud binding are strictly additive, env-triggered behaviours.
- **NFR4 — Cyber hygiene:** TLS-only (Cloud Run provides it), non-root container, tokens
  never logged, pinned `uv.lock`, `.dockerignore` excludes secrets and caches.
- **NFR5 — Segal gate:** ruff clean, every new `src/` file ≤ 150 lines, ≥ 85% coverage on
  new testable code, no hard-coded grid/port/model values in new code, no secrets committed.
- **NFR6 — uv-only:** all dependency changes via `uv`; do not hand-edit `requirements.txt`.

---

## 6. In scope / Out of scope

**In scope:**
- Containerising the two existing MCP servers (no change to tool surface or game rules).
- Per-server static bearer-token auth gate, env-injected, offline-testable.
- Cloud Run `0.0.0.0:$PORT` binding with local config fallback.
- `HttpGateway` auth-header and env-driven public URL wiring.
- Deploy runbook, `.env.example`, hygiene checklist, `tests/test_cloud/`.
- ROADMAP and README pointers for the two live URLs (operator step after deploy).

**Out of scope (deferred):**
- Game logic, strategy, NL/LLM behaviour, GUI — unchanged.
- OAuth/JWT flows, per-user identity, rate limiting, secret-manager integration.
- Deploying the orchestrator/LLM to the cloud (LLM MUST stay client-side — hard constraint).
- Gmail report email (Step 8).

---

## 7. Acceptance criteria

1. **[AC1 — Dockerfile]** A single `Dockerfile` builds an image that runs the Cop server with
   `MCP_ROLE=cop` and the Thief server with `MCP_ROLE=thief`, binding `0.0.0.0:$PORT` when
   `PORT` is set. Verified by `docker build` success + `docker run --env MCP_ROLE=cop --env
   PORT=8080 -p 8080:8080 ...` smoke-test (or, if Docker is unavailable, by reading the
   Dockerfile and confirming the CMD and ENV declarations match the contract).

2. **[AC2 — Auth gate: 401 enforcement]** With `COP_AUTH_TOKEN` or `THIEF_AUTH_TOKEN` set,
   a request with no token or a wrong token is rejected (HTTP 401). A request with the
   correct token succeeds. Proven by offline tests that call the FastMCP `StaticBearerVerifier`
   directly (AccessToken on match, `None` → 401 on mismatch) and assert the verifier attaches
   to the server only when a token is set (no live server required).

3. **[AC3 — Auth gate: backward compatibility]** With token env vars unset, both servers and
   all 152 existing in-memory and local tests run unchanged — no token required, no new
   assertions broken.

4. **[AC4 — HttpGateway auth header]** `HttpGateway(url, "cop", telemetry, auth_token="t")`
   sends `Authorization: Bearer t` on every tool call; `HttpGateway(url, "cop", telemetry)`
   (no token) sends no auth header. Covered by a test that monkeypatches
   `fastmcp.Client.__aenter__` or inspects the constructed client's auth attribute.

5. **[AC5 — Env-driven URL / token assembly]** `gateway_from_env` (or equivalent in
   `__main__`) reads `COP_SERVER_URL`/`THIEF_SERVER_URL` and `COP_AUTH_TOKEN`/
   `THIEF_AUTH_TOKEN` from env; falls back to config URL with no token when env is absent.
   Covered by a test that sets and clears env vars.

6. **[AC6 — No secrets in git]** A grep guard test asserts that the strings `COP_AUTH_TOKEN=`,
   `THIEF_AUTH_TOKEN=`, no bare token values, and no public Cloud Run URL (`run.app`) appear
   in committed `src/`, `config.yaml`, `deploy/`. `.env` is listed in `.gitignore`.

7. **[AC7 — Container hygiene]** The `Dockerfile` creates a non-root user and switches to it
   before `CMD`. `uv.lock` pins all deps. `.dockerignore` excludes `runs/`, `.env`,
   `__pycache__`, `.venv`. Verified by inspection of the three files.

8. **[AC8 — DEPLOY.md runbook]** `docs/step7_cloud_deploy/DEPLOY.md` contains copy-paste
   `gcloud run deploy` commands for both services with all required flags (`--image`, `--region`,
   `--platform=managed`, `--allow-unauthenticated`, `--set-env-vars`) plus a curl smoke-test
   block showing `401` without the token and `200` with. Verified by reading the file.

9. **[AC9 — Segal gate]** `uv run ruff check src/ tests/test_cloud/` passes. Every new
   `src/` file is ≤ 150 lines. `uv run pytest -q tests/test_cloud/ --cov=src.mcp_servers.auth
   --cov-fail-under=85` passes. No hard-coded port, grid size, or model value in new code.

10. **[AC10 — Full suite backward compatibility]** `uv run pytest -q` reports ≥ 152 tests
    passing. The existing suite is the regression fence for backward compatibility.

11. **[AC11 — MANUAL: live Cloud Run deploy]** (Operator step — not automated.) Both services
    are actually deployed to Cloud Run and the **two public HTTPS URLs** are recorded in
    `README.md`, with a `curl` or `ping` showing HTTP 401 without the token and a valid
    JSON tool response with the correct bearer token. Requires `gcloud auth login` and a
    Google Cloud billing account. This criterion is NOT a code box in the TODO.

---

## 8. Dependencies

- **Upstream (needs):**
  - Step 2: `build_cop_server`/`build_thief_server`, `FastMCP`, `mcp.run()` pattern.
  - Step 3: `HttpGateway`/`ServerGateway` protocol, `InMemoryGateway`, `Telemetry`.
  - Step 2+: `load_config`, `Config`, `config.servers.{cop,thief}.{host,port}`.
  - SDK reference: `SDK_REFERENCE_fastmcp_auth.md` (verified API shapes for auth/client).
- **Downstream (unblocks):**
  - Step 8 (Gmail API): no structural dependency; leaves a reusable `.env`/env-driven
    pattern the operator can reference.
  - README: the two public HTTPS URLs and the curl proof are the main README artifact.

---

## 9. Acceptance-coverage view

| Acceptance criterion | Primary evidence | Secondary evidence |
|---------------------|------------------|--------------------|
| AC1 Dockerfile | `docker build` + `docker run` smoke | Read Dockerfile CMD/ENV |
| AC2 Auth gate 401/200 | `tests/test_cloud/test_auth.py` | `SDK_REFERENCE_fastmcp_auth.md §2` |
| AC3 Backward compat | `uv run pytest -q` ≥ 152 pass | no-env server starts unchanged |
| AC4 HttpGateway header | `tests/test_cloud/test_gateway.py` | `SDK_REFERENCE §1` |
| AC5 Env URL/token assembly | `tests/test_cloud/test_gateway.py` | `orchestrator/__main__.py` |
| AC6 No secrets in git | `tests/test_cloud/test_static_guards.py` | `.gitignore` inspection |
| AC7 Container hygiene | Dockerfile inspection + .dockerignore | `uv.lock` present |
| AC8 DEPLOY.md runbook | `DEPLOY.md` file existence + content check | copy-paste gcloud commands |
| AC9 Segal gate | `ruff check` + coverage ≥85% + ≤150 lines | no-hardcode guard |
| AC10 Full suite compat | `uv run pytest -q` | no changes to game/agent modules |
| AC11 Live deploy (MANUAL) | README URLs + curl proof | operator note in Developer session |

---

## 10. References

- `docs/step7_cloud_deploy/DECISION_step7_cloud_deploy.md`
- `docs/step7_cloud_deploy/SDK_REFERENCE_fastmcp_auth.md`
- `docs/_system/WORKFLOW.md`
- `src/orchestrator/gateway.py` — `HttpGateway`, `_BaseGateway`, `InMemoryGateway`
- `src/mcp_servers/cop_server.py`, `thief_server.py` — `build_*_server`, `__main__`
- `src/game/config.py` — `Config`, `load_config`, `config.servers.{cop,thief}.{host,port}`
- `config.yaml` — `servers:` block; no new keys for secrets/URLs
- Assignment §13 Table 4 (step 7)
