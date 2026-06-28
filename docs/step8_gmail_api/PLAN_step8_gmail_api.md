# PLAN — Step 8: Gmail API Reporting

- **Status:** triplet-built
- **Source:** `DECISION_step8_gmail_api.md`, `SDK_REFERENCE_gmail.md`, `PRD_step8_gmail_api.md`

---

## 1. Architecture overview

Step 8 is purely a client-side reporting add-on: it does not change game logic, agents,
strategy, prompts, or the GUI. It adds a new `src/reporting/` package and a single
fail-soft hook call in the orchestrator. The two FastMCP servers, the gateway, and the
referee are untouched.

```
  src/orchestrator/__main__.py
    result = await run_series(...)              # unchanged
    replay_log.close()                           # unchanged
    print("=== Series Result ===") ...           # unchanged
    s = telemetry.summary()                      # unchanged
    print("=== Telemetry ===") ...               # unchanged
    maybe_send_report(result, s, config, replay_log.path)   # NEW (fail-soft, gated)
        │
        ▼
  src/reporting/
    report.py        build_report(...)  -> dict (pure, deterministic w/ injectable now)
    gmail_client.py  GmailSender.send(to, subject, body) -> msg_id  (base64url raw MIME)
    auth.py          build_credentials(...) -> Credentials | None   (token cache + refresh)
    __main__.py      CLI: `auth` (one-time OAuth) | `send` (ad-hoc send)
        │
        ▼  (only when config.report['enabled'] AND token.json exists)
  Gmail API v1  users().messages().send(userId='me', body={'raw': <base64url RFC2822>})
```

**Key invariants:**
- The hook is **fail-soft**: a reporting failure can never mask a good series result.
- The gate is **default-off** (`enabled: false`) + **token-absent no-op** ⇒ the 165 prior
  tests stay green and no dev run sends.
- The body is **JSON-only** (`Content-Type: application/json`); the JSONL replay log is
  referenced by filename only, never inlined or attached.
- The sender is the authenticated OAuth account (implicit `from`); `report.to` is the
  recipient (the lecturer) — never a code literal.

---

## 2. File / module layout

```
src/reporting/__init__.py           (new)   — package marker (empty)
src/reporting/report.py             (new)   — pure JSON report builder (build_report)
src/reporting/gmail_client.py       (new)   — GmailSender wrapping gmail.users().messages().send
src/reporting/auth.py               (new)   — build_credentials (token cache + refresh) + cmd_auth
src/reporting/__main__.py           (new)   — CLI: `auth` (OAuth login) | `send` (ad-hoc)
src/orchestrator/__main__.py        (edit)  — add maybe_send_report(...) call after series
src/game/config.py                  (edit)  — add Config.report: dict | None + loader wiring
config.yaml                         (edit)  — add report: block (enabled/to/subject/paths)
.gitignore                          (edit)  — add secrets/, gmail_credentials.json, gmail_token.json
.env.example                        (edit)  — document REPORT_ENABLED/REPORT_TO/GMAIL_*_PATH
pyproject.toml                      (edit)  — add 3 google deps to [dependency-groups].dev
tests/test_reporting/__init__.py    (new)   — package marker (empty)
tests/test_reporting/test_report.py       (new)   — build_report shape + resize + no-secrets
tests/test_reporting/test_gmail_client.py (new)   — stubbed GmailSender.send (raw decode)
tests/test_reporting/test_gating.py       (new)   — gate no-op, fail-soft, env overrides, hygiene
```

No changes to `src/game/engine.py`, `src/orchestrator/recorders.py`,
`src/orchestrator/referee.py`, `src/orchestrator/gateway.py`, `src/agents/`,
`src/strategy/`, `src/gui/`, `src/mcp_servers/`.

---

## 3. Data model / key structures

### Report JSON schema (DECISION §7, verbatim)

```json
{
  "schema_version": 1,
  "generated_at": "<ISO8601 UTC>",
  "config": {
    "grid_size": [5, 5],
    "num_games": 6,
    "max_moves": 25,
    "max_barriers": 5,
    "scoring": {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}
  },
  "agents": {
    "cop": "llm", "thief": "llm",
    "llm_model": "claude-haiku-4-5-20251001",
    "observation_mode": "noisy"
  },
  "series": {
    "group_a_total": 30, "group_b_total": 30,
    "sub_games": [
      {"index": 1, "winner": "COP", "cop_score": 20, "thief_score": 5, "moves_used": 7, "a_was_cop": true}
    ]
  },
  "telemetry": { "calls": 84, "avg_ms": 1.2, "p95_ms": 3.0, "boot_ping": {"cop_ms": 5.0, "thief_ms": 5.0},
                 "llm_calls": 48, "llm_avg_ms": 600.0, "llm_input_tokens": 12000,
                 "llm_output_tokens": 3000, "llm_estimated_cost_usd": 0.012 },
  "replay_log": "runs/20260627T120000Z.jsonl"
}
```

Notes on the schema vs the live code:
- `generated_at` is the only non-deterministic field; `build_report` accepts an injectable
  `now: datetime | None` so tests fix it (or strip it).
- The `telemetry` field is the `dict` passed in (i.e. `Telemetry.summary()`'s return)
  **verbatim**. The live `Telemetry.summary()` (`src/orchestrator/recorders.py`) returns
  two extra cache-token keys (`llm_cache_creation_input_tokens`,
  `llm_cache_read_input_tokens`) beyond the illustrative block above; those are carried
  through unchanged. The §7 block is illustrative; the test fixture uses the real
  `summary()` shape. (See §8 Risks.)
- `replay_log` is the `replay_path` argument verbatim — the full path from
  `ReplayLog.path` (e.g. `runs/20260627T120000Z.jsonl`).
- `a_was_cop` per sub-game comes from the `a_was_cop_per_subgame` kwarg; the orchestrator
  derives it as `[sg.cop_group == "A" for sg in result.sub_games]` (see §4 + §5).

### Config block (default in `config.yaml`)

```yaml
report:
  enabled: false        # flip to true + run `python -m src.reporting auth` once for the live send
  to: "rmisegal+uoh26b@gmail.com"
  subject: "HW6 Cop&Thief MCP series report"
  credentials_path: "secrets/gmail_credentials.json"   # OAuth client secret (Google Cloud Console)
  token_path: "secrets/gmail_token.json"               # refresh token (one-time login)
```

`Config.report: dict | None` is a trailing-optional field (same pattern as
`gui: dict | None = None`, `strategy: dict | None = None`). Env overrides
(`REPORT_ENABLED`, `REPORT_TO`, `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`) win over
config values; the loader applies them in `load_config` (or the reporter resolves them at
call time — see §4).

### Env contract

| Env var | Meaning |
|---------|---------|
| `REPORT_ENABLED` | `true`/`false` → flips the gate (wins over `config.report['enabled']`) |
| `REPORT_TO` | overrides `config.report['to']` (recipient) |
| `GMAIL_CREDENTIALS_PATH` | overrides `config.report['credentials_path']` |
| `GMAIL_TOKEN_PATH` | overrides `config.report['token_path']` (resolved token path for the gate) |

---

## 4. Component design

### `src/reporting/report.py` — pure builder (≤ 150 lines)

- **Responsibility:** turn a `SeriesResult` + telemetry dict + `Config` + replay path into
  the §7 report dict. No I/O, no network, no secrets.
- **Key function:**
  - `build_report(series_result: SeriesResult, telemetry: dict, config: Config,
    replay_path: str, *, a_was_cop_per_subgame: list[bool], now: datetime | None = None)
    -> dict` — pure. Builds `config`/`agents`/`series`/`telemetry`/`replay_log` blocks;
    `generated_at = (now or datetime.now(timezone.utc)).isoformat()`. Reads
    `config.agents["cop"]`, `config.agents["thief"]`, `config.agents["llm"]["model"]`,
    `config.observation["mode"]`. Per sub-game: `index`, `winner`, `cop_score`,
    `thief_score`, `moves_used`, `a_was_cop` (from the kwarg list, fallback to
    `sg.cop_group == "A"` if the list is shorter).
- **Determinism:** `now` is injectable; tests pass a fixed `datetime` or strip
  `generated_at`.
- **No secrets:** never reads `credentials_path`/`token_path`/tokens; the `replay_log`
  field is the replay path (a non-secret run artifact).

### `src/reporting/gmail_client.py` — GmailSender (≤ 150 lines)

- **Responsibility:** wrap `gmail.users().messages().send` for a JSON-only body.
- **Key class:**
  - `class GmailSender:` `__init__(self, credentials_path, token_path)`; stores paths and
    the `gmail.send` scope.
  - `send(self, to: str, subject: str, body: dict) -> str` — calls
    `build_credentials(self._credentials_path, self._token_path, scopes=self._scopes)`
    (returns `None` if no token → caller treats as no-op); builds an `EmailMessage` with
    `To`/`Subject`/`Content-Type: application/json` and `json.dumps(body)` as the content;
    `raw = base64.urlsafe_b64encode(message.as_bytes()).decode()`; `service =
    build("gmail","v1",credentials=creds)`; `sent = service.users().messages().send(
    userId="me", body={"raw": raw}).execute()`; returns `sent["id"]`.
- **Why `EmailMessage` + `urlsafe_b64encode`:** confirmed by the official
  `gmail_send_message` sample (SDK ref §1.2). Padding is retained (the API accepts it).
- **No hard-coding:** `to`/`subject` come from the caller (config), never literals.

### `src/reporting/auth.py` — credentials + one-time login (≤ 150 lines)

- **Responsibility:** token-cache load/refresh + the one-time OAuth login.
- **Key functions:**
  - `build_credentials(credentials_path, token_path, *, scopes) -> Credentials | None` —
    returns `None` if `token_path` does not exist (gating); else
    `Credentials.from_authorized_user_info(json.load(fh), scopes=scopes)`; if
    `creds.expired and creds.refresh_token`: `creds.refresh(Request())` and re-`to_json()`
    to persist. Imports: `Credentials` from `google.oauth2.credentials`, `Request` from
    `google.auth.transport.requests`.
  - `cmd_auth(credentials_path, token_path, *, scopes) -> None` —
    `InstalledAppFlow.from_client_secrets_file(credentials_path, scopes=scopes)`
    `.run_local_server(port=0)`; writes `creds.to_json()` to `token_path`. Marked
    `# pragma: no cover` (manual AC9; no `credentials.json` in CI).
- **Scope:** `SCOPES = ["https://www.googleapis.com/auth/gmail.send"]` (minimal).

### `src/reporting/__main__.py` — CLI (≤ 150 lines)

- **Responsibility:** `python -m src.reporting auth` (one-time login) and
  `python -m src.reporting send` (ad-hoc send for the operator).
- **Behavior:** parses `sys.argv[1]`; `auth` → `cmd_auth(...)` with paths from
  config/env; `send` → build a report from the last replay log (or a fixture) and send
  it. Both paths are manual operator tools; `# pragma: no cover` on the live paths.
- **Config:** loads `config.yaml` via `load_config`; resolves paths with env overrides.

### `src/orchestrator/__main__.py` — the hook (edit)

- After the existing `print(f"Replay log: {replay_log.path}")` line, add:
  ```python
  from src.reporting.gmail_client import GmailSender
  from src.reporting.report import build_report
  ...
  maybe_send_report(result, s, config, replay_log.path)
  ```
  where `maybe_send_report` (defined in `gmail_client.py` or a small `_gating` helper)
  resolves the gate + paths from env/config and calls `GmailSender.send` inside a
  `try/except Exception` that logs and swallows. See §5 for the exact flow.
- **Backward compatibility:** with `enabled: false` (default) and no token, the call is a
  no-op that returns immediately — the 165 prior tests are unaffected.

### `src/game/config.py` + `config.yaml` — the `report:` block (edit)

- Add `report: dict | None = None` as a trailing-optional field on `Config` (after
  `gui: dict | None = None`).
- Loader: read `data.get("report")` into `Config.report` (merge with a `_DEFAULT_REPORT`
  dict so `enabled` defaults to `false` even if the block is partially present). Apply
  env overrides (`REPORT_ENABLED` → `report['enabled']`, `REPORT_TO` → `report['to']`,
  `GMAIL_CREDENTIALS_PATH` → `report['credentials_path']`, `GMAIL_TOKEN_PATH` →
  `report['token_path']`) so tests can flip the gate by setting env.
- Add the `report:` block to `config.yaml` with the §3 defaults.

### `tests/test_reporting/` (all offline)

1. **`test_report.py`** — pure builder:
   - full-shape snapshot on a fixed `SeriesResult` + telemetry dict + `Config` + replay
     path, with `now=` fixed (or `generated_at` stripped) → asserts every field.
   - resize: a 3×3 / `num_games=2` fixture → correct smaller report.
   - no-secrets: serialize the report, assert no `token`, `credentials`, `api_key`,
     `secret` substrings.
2. **`test_gmail_client.py`** — stubbed send:
   - monkeypatch `googleapiclient.discovery.build` to return a fake service whose
     `.users().messages().send(userId='me', body={'raw': ...}).execute()` returns
     `{"id": "stub-id"}`; monkeypatch `build_credentials` to return a dummy `Credentials`.
   - assert: the returned id is `"stub-id"`; the `raw` field `base64.urlsafe_b64decode`s
     to a message containing `To: <recipient>`, `Subject: <subject>`,
     `Content-Type: application/json`, and the JSON body; no real network call.
3. **`test_gating.py`** — gate + fail-soft + env + hygiene + `build_credentials`:
   - `enabled=false` → `maybe_send_report` does not construct the service (patch
     `discovery.build`, assert never called).
   - token absent → same no-op.
   - `enabled=true` + token present (tmp file) → `GmailSender.send` is called with the
     built report (patch the sender AND `build_report`, since the `_Cfg` stub lacks the
     attrs the real builder reads — the builder shape is already covered by
     `test_report.py`).
   - fail-soft: inject a `send` that raises → `maybe_send_report` returns without raising
     (patch `build_report` so the swallowed error is the `send` failure, not an
     `AttributeError` from the builder).
   - env precedence: `REPORT_ENABLED=true` flips the gate; `GMAIL_TOKEN_PATH` overrides
     the resolved token path.
   - `build_credentials`: no-token → returns `None`; expired+`refresh_token` → refreshes
     and re-persists (covers `auth.py`, else the coverage gate fails there).
   - static guards: `.gitignore` has `secrets/` + the two filenames; `.env.example` has
     the four env vars; `config.yaml` has no real secret; each `src/reporting/` file ≤ 150
     lines; no hard-coded lecturer address in `src/`.

---

## 5. Control flow / sequences

### Local run / CI (default, no send)

```
python -m src.orchestrator
  → load_config("config.yaml")            # config.report = {"enabled": False, ...}
  → run_series(...) -> result              # unchanged
  → replay_log.close(); print series + telemetry + replay_log.path   # unchanged
  → maybe_send_report(result, telemetry.summary(), config, replay_log.path)
        → resolve report block: config.report (env overrides applied in loader)
        → if not report.get("enabled"): log "report disabled"; return          # NO-OP
        → token_path = env GMAIL_TOKEN_PATH or report["token_path"] or "secrets/gmail_token.json"
        → if not os.path.exists(token_path): log "no token"; return            # NO-OP
        → try:
            body = build_report(result, telemetry, config, replay_path,
                                a_was_cop_per_subgame=[sg.cop_group=="A" for sg in result.sub_games])
            sender = GmailSender(report["credentials_path"], token_path)
            msg_id = sender.send(report["to"], report["subject"], body)
            print(f"Report sent: message id {msg_id}")
          except Exception as exc:                                # FAIL-SOFT
            print(f"Report send failed (non-fatal): {exc}")
```

The 165 prior tests never set `REPORT_ENABLED=true` and never create a token file ⇒ the
hook returns at the first or second guard. No real send, no service construction.

### Live send (manual operator, AC9)

```
# one-time:
python -m src.reporting auth     # browser OAuth; writes secrets/gmail_token.json
# flip the gate:
#   edit config.yaml: report.enabled: true   (or: export REPORT_ENABLED=true)
python -m src.orchestrator
  → ... run_series ...
  → maybe_send_report(...)
        → enabled=True, token exists
        → build_credentials(...)  (refresh if expired)  -> Credentials
        → build_report(...) -> dict
        → GmailSender.send(to, subject, body)
              → EmailMessage(To, Subject, Content-Type: application/json, json.dumps(body))
              → raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
              → service = build("gmail","v1",credentials=creds)
              → service.users().messages().send(userId="me", body={"raw": raw}).execute()
              → return sent["id"]
        → print(f"Report sent: message id {id}")
```

---

## 6. Config additions

| Key | Default | Used by |
|-----|---------|---------|
| `report.enabled` | `false` | `maybe_send_report` gate |
| `report.to` | `"rmisegal+uoh26b@gmail.com"` | `GmailSender.send` recipient |
| `report.subject` | `"HW6 Cop&Thief MCP series report"` | `GmailSender.send` subject |
| `report.credentials_path` | `"secrets/gmail_credentials.json"` | `build_credentials` / `cmd_auth` |
| `report.token_path` | `"secrets/gmail_token.json"` | `build_credentials` / the gate |

Env overrides (win over config): `REPORT_ENABLED`, `REPORT_TO`,
`GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`.

`pyproject.toml` `[dependency-groups].dev` additions: `google-auth`, `google-auth-oauthlib`,
`google-api-python-client`.

---

## 7. Test strategy

- **Unit (offline):** `test_report.py` covers the pure builder (shape + resize +
  no-secrets) with a fixed `now`/telemetry dict. `test_gmail_client.py` monkeypatches
  `discovery.build` and `build_credentials` so no network and no real credentials. All
  deterministic.
- **Gating (offline):** `test_gating.py` covers the gate (enabled/token-absent no-op),
  fail-soft (raising sender), env-override precedence, and the static hygiene guards
  (`.gitignore`, `.env.example`, line counts, no real secrets in `config.yaml`).
- **Regression:** `uv run pytest -q` (the full existing 165-test suite) must continue
  passing — the default-off gate + token-absent no-op is the fence.
- **Coverage gate:** `uv run pytest -q tests/test_reporting/ --cov=src.reporting
  --cov-fail-under=85`. The only uncovered line is the live OAuth/send path in
  `auth.cmd_auth` / `__main__`, marked `# pragma: no cover` (manual AC9).
- **Manual acceptance:** the operator runs `python -m src.reporting auth`, flips
  `enabled: true`, runs a real series, and records the sent message id in the README
  (AC9).

---

## 8. Risks & mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Gmail API `raw` shape wrong (padded vs unpadded base64url) | Low | Official `gmail_send_message` sample uses `base64.urlsafe_b64encode(...).decode()` **with padding retained** (SDK ref §1.2). The TODO code copies that sample verbatim; do not strip padding. |
| `google-api-python-client` v1 discovery deprecated | Low | Confirmed current (SDK ref §6): the 2026 official Gmail sample still uses `build("gmail","v1",...)`. `google-genai` is the Gemini SDK, unrelated to Gmail. |
| Gate leaks a send into the 165-test suite | Medium | Gate = `config.report['enabled'] is True` **AND** token file exists. Default `enabled: false`; no token in CI. `test_gating.py` proves no service construction when disabled. |
| `maybe_send_report` raises into the orchestrator | Medium | Entire send path wrapped in `try/except Exception` that logs and swallows; `test_gating.py` injects a raising sender and asserts no propagation. |
| Non-deterministic `generated_at` breaks snapshot tests | Medium | `build_report(now=...)` is injectable; tests pass a fixed `datetime` or strip `generated_at`. |
| `Telemetry.summary()` has extra cache-token keys vs §7 block | Low | `build_report` embeds the passed telemetry dict verbatim; §7 block is illustrative. The test fixture uses the real `summary()` shape. No data loss; no schema mismatch. |
| Real `credentials.json`/`token.json` committed to git | Low | `.gitignore` gains `secrets/` + the two filenames before any credential file can exist; `test_gating.py` asserts they are ignored. |
| Lecturer address hard-coded in source | Low | `report.to` default lives only in `config.yaml`; `test_gating.py` grep guard asserts the address is not a literal in `src/reporting/`. |
| Secrets leak into the report body | Low | `build_report` never reads token/credential paths; `test_report.py` greps the serialized JSON for `token`/`secret`/`api_key`. |

---

## 9. Work breakdown (macro order)

1. **Deps + config + hygiene:** `pyproject.toml` deps, `config.yaml` `report:` block,
   `Config.report` field + env overrides, `.gitignore`, `.env.example`.
2. **`report.py`:** pure `build_report` (the most test-loaded module).
3. **`auth.py` + `gmail_client.py`:** `build_credentials`, `cmd_auth`, `GmailSender.send`,
   `maybe_send_report`.
4. **`__main__.py` (reporting CLI):** `auth` + `send` subcommands.
5. **Orchestrator hook:** wire `maybe_send_report` into `src/orchestrator/__main__.py`.
6. **Tests:** `test_report.py`, `test_gmail_client.py`, `test_gating.py`.
7. **Gate:** ruff, coverage ≥85%, ≤150-line guards, full suite ≥165 pass.
8. **Manual operator (AC9):** OAuth login + live send + README.

---

## 10. Acceptance-coverage matrix

| AC | Satisfying TODO phase/boxes | Test / check |
|----|------------------------------|--------------|
| AC1 Report shape | Phase B (report.py) | `test_report.py::test_build_report_full_shape` |
| AC2 Resizable | Phase B | `test_report.py::test_build_report_resizable_3x3` |
| AC3 No secrets in body | Phase B | `test_report.py::test_report_has_no_secrets` |
| AC4 GmailSender stubbed send | Phase C (gmail_client.py) | `test_gmail_client.py::test_send_stubbed_returns_id_and_raw` |
| AC5 Gating no-op | Phase D (maybe_send_report) | `test_gating.py::test_noop_when_disabled` / `test_noop_when_no_token` |
| AC6 Fail-soft | Phase D | `test_gating.py::test_fail_soft_swallows_send_error` |
| AC7 Orchestrator hook + suite | Phase D (hook wiring) | full `uv run pytest -q` ≥ 165 pass |
| AC8 Config + env overrides | Phase A (config) | `test_gating.py::test_env_overrides_flip_gate_and_path` |
| AC9 Live send (MANUAL) | Phase E (CLI) + operator | README "Email reporting" + sent message id |
| AC10 Hygiene artifacts | Phase A | `test_gating.py::test_gitignore_and_env_example` |
| AC11 Segal gate | Phase F | `ruff check` + coverage ≥85% + ≤150-line guard |
| AC12 Deps | Phase A | `pyproject.toml` + `uv.lock` inspection |
