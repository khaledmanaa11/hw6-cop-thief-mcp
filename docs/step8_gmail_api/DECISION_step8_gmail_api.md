# DECISION — Step 8: Gmail API Reporting

- **Roadmap position:** step 8 of 8 (`step8_gmail_api`) — the final step.
- **Date discussed:** 2026-06-27
- **Status:** decision-written
- **Assignment references:** §13 (Table 4, engineering priority order — step 8 = Gmail API reporting), §report email target `rmisegal+uoh26b@gmail.com` (JSON body only), §6 hard constraints (no hard-coding, JSON-only email report at end of a 6-sub-game series).

## 1. What this step is (one paragraph)

After a 6-sub-game series finishes, the orchestrator currently only prints a
summary to stdout. Step 8 adds a **reporter** that builds a **JSON-only**
report from the series result (+ telemetry + config) and sends it as the
**email body** (not an attachment) to the fixed lecturer address, via the
**Gmail API** with OAuth2. Sending is **always-on when credentialed**, but
defaults to disabled in config and is a no-op without a refresh token, so the
existing 165-test suite stays green and no dev run accidentally mails the
lecturer. The actual live send to the lecturer is a deferred manual operator
step (one-time browser OAuth login + a real series run), matching the
convention used for the Step 5 live-LLM run, the Step 6 screenshot, and the
Step 7 gcloud deploy.

## 2. What it adds to the project

- New client-tier package `src/reporting/`:
  - `report.py` — pure, deterministic JSON report builder
    (`build_report(...) -> dict`); unit-tested, no network.
  - `gmail_client.py` — `GmailSender` wrapping the Gmail API v1
    `users().messages().send(...)` call with OAuth2 credentials.
  - `auth.py` — one-time OAuth2 user-consent flow that produces a refresh
    `token.json` from a downloaded `credentials.json`.
  - `__main__.py` — CLI entry (`python -m src.reporting`) to (a) run the
    one-time OAuth login, and (b) send a report for an existing replay log /
    the last run.
- A trailing-optional `report:` config block (`enabled`, `to`, `subject`,
  `credentials_path`, `token_path`) added to `config.yaml` + a `Config.report`
  field, following the same trailing-optional pattern as `gui:`/`strategy:`.
- Env overrides for all secrets/paths (`GMAIL_CREDENTIALS_PATH`,
  `GMAIL_TOKEN_PATH`, `REPORT_TO`, `REPORT_ENABLED`) — secrets never in
  `config.yaml` or git.
- A `maybe_send_report(...)` hook wired into `src/orchestrator/__main__.py`
  after the series result + telemetry summary are computed.
- `.gitignore` entries for Google credential files.
- New dev deps: `google-auth`, `google-auth-oauthlib`,
  `google-api-python-client`.

## 3. Scope

**In scope:**
- Pure JSON report builder (header + per-sub-game + totals + telemetry +
  replay-log filename).
- Gmail API v1 OAuth2 send path (scope `gmail.send`), sender = the
  authenticated Google account.
- One-time OAuth login CLI.
- Orchestrator hook (`maybe_send_report`), gated on `enabled` + token
  presence.
- Tests: pure builder, stubbed Gmail send, gating no-op behavior.
- `.gitignore` + `.env.example` updates for credential paths.

**Out of scope (deferred):**
- The **live send** to the real lecturer address → deferred manual operator
  artifact (AC9), like Step 5/6/7 manual artifacts.
- Reading/inlining the full per-ply JSONL into the body → the JSONL is a
  separate file deliverable; only its filename is referenced in the report.
- Attaching the JSONL as an email attachment → rejected: the assignment says
  "JSON body only".
- Inter-group bonus competition JSON report → separate optional deliverable
  (ROADMAP cross-cutting), not this step.

## 4. Chosen approach (and what we rejected)

**Decision:** Gmail API v1 + OAuth2 user-consent flow, scope `gmail.send`;
build a rich-but-compact pure-JSON report body; send always-on when
`report.enabled=true` AND a refresh token is present; reference the replay
log by filename only.

**Why:** the step is literally named "*Gmail API*" so SMTP is out; personal
`@gmail.com` can't be reached by service accounts so OAuth2 user-consent is
the only real option. Always-on-when-credentialed is the Director's choice —
the safety net is `enabled` defaulting to `false` plus no token in the test
env, so the 165 tests stay green and dev runs never mail the lecturer. Rich-
but-compact gives the lecturer the orchestration-relevant context (config,
agent types, observation mode, telemetry) without bloating the body or
duplicating the JSONL file.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Gmail API v1 + OAuth2 user-consent, scope `gmail.send` | ✅ chosen | The real "Gmail API"; works for personal `@gmail.com`; minimal scope. |
| SMTP + 16-char app password | ❌ rejected | Not the Gmail API — dodges the graded point; contradicts the step name. |
| Service account (JSON key) | ❌ rejected | Only works on Google Workspace domains, cannot send from/to personal `@gmail.com`. |
| `--report` CLI flag trigger | ❌ rejected (Director chose always-on) | Director prefers no-flag; safety net is `enabled=false` default + absent token. |
| Inline full JSONL replay into body | ❌ rejected | Body too large; duplicates the JSONL file deliverable; risks Gmail size limits. |
| Attach JSONL as MIME attachment | ❌ rejected | Assignment says "JSON body only". |

## 5. Dependencies & interfaces

- **Consumes from prior steps:**
  - `SeriesResult` (`sub_games: list[SubGameResult(winner, cop_score, thief_score, moves_used)]`, `group_a_total`, `group_b_total`) — `src/game/engine.py`.
  - `Telemetry.summary()` (`calls`, `avg_ms`, `p95_ms`, `boot_ping`, `llm_*`, `llm_estimated_cost_usd`) — `src/orchestrator/recorders.py`.
  - `Config` (`grid_size`, `num_games`, `max_moves`, `max_barriers`, `scoring`, `agents`, `observation`) — `src/game/config.py`.
  - The JSONL replay-log path (`ReplayLog.path`) — produced by Step 3; referenced by filename only.
- **Exposes to later steps:** none — this is the final step. The report JSON
  schema is the project's terminal deliverable shape.
- **Touches config keys:** new trailing-optional `report:` block
  (`enabled`, `to`, `subject`, `credentials_path`, `token_path`); no change
  to existing keys. `output.run_dir` is reused (replay-log path lives there).

## 6. Binding constraints (from the assignment)

- **JSON-only email body** — the report is sent as the email body, not as an
  attachment; no MIME attachment of the JSONL.
- **No hard-coding** — recipient, subject, credentials/token paths live in
  config/env, not in code. The lecturer address is the `report.to` *default*
  in `config.yaml`, never a code literal.
- **End of a 6-sub-game series** — the send happens after `run_series`
  returns, never mid-series.
- **Cyber hygiene (carried from Step 7)** — Google credentials are secrets:
  `credentials.json`/`token.json` live on disk only, gitignored, never in
  `config.yaml`/git/logs; OAuth scope is the minimal `gmail.send`; the report
  body contains no secrets (no tokens, no API keys).

## 7. Key design decisions

- **Files/modules:**
  - `src/reporting/__init__.py`
  - `src/reporting/report.py` — pure builder.
  - `src/reporting/gmail_client.py` — Gmail API send.
  - `src/reporting/auth.py` — one-time OAuth login.
  - `src/reporting/__main__.py` — CLI.
  - `src/orchestrator/__main__.py` — add the `maybe_send_report` call.
  - `src/game/config.py` + `config.yaml` — add `report:` block + `Config.report`.
  - `.gitignore`, `.env.example` — credential-file entries.
  - `tests/test_reporting/` — `test_report.py`, `test_gmail_client.py`, `test_gating.py`.
- **Core data structures:**
  - The report JSON (rich-but-compact). Concrete shape:
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
    `generated_at` is the only non-deterministic field; tests use a fixed
    clock or strip it. No secrets appear anywhere.
- **Key signatures (intent):**
  - `build_report(series_result: SeriesResult, telemetry: dict, config: Config, replay_path: str, *, a_was_cop_per_subgame: list[bool]) -> dict` — pure; returns the dict above.
  - `class GmailSender:` `__init__(self, credentials_path, token_path)`; `send(self, to: str, subject: str, body: dict) -> str` — base64url-encodes `To`/`Subject`/`Content-Type: application/json` + the JSON body into a `raw` message, calls `gmail.users().messages().send(userId='me', body={'raw': ...})`, returns the sent message id.
  - `build_credentials(credentials_path, token_path, *, scopes) -> google.oauth2.credentials.Credentials` — loads `token.json` if present (refreshes), else raises/returns `None` so the caller can no-op.
  - `maybe_send_report(series_result, telemetry, config, replay_path) -> None` — no-op unless `config.report['enabled']` and token present; else builds + sends; logs the message id or the skip reason. Never raises into the orchestrator (fail-soft: a report failure must not crash the series output).
- **Gating rule (load-bearing for the 165-test suite):**
  `maybe_send_report` sends **iff** `config.report['enabled'] is True` **AND** the token file exists at the resolved path. Default `enabled: false`, no token in the test env ⇒ all existing tests stay green and no dev run sends. Resolved path = env override (`GMAIL_TOKEN_PATH`) else `config.report['token_path']` else default `secrets/gmail_token.json`.
- **Config block (default in `config.yaml`):**
  ```yaml
  report:
    enabled: false        # flip to true + run `python -m src.reporting auth` once for the live send
    to: "rmisegal+uoh26b@gmail.com"
    subject: "HW6 Cop&Thief MCP series report"
    credentials_path: "secrets/gmail_credentials.json"   # OAuth client secret (downloaded from Google Cloud Console)
    token_path: "secrets/gmail_token.json"               # refresh token (generated by one-time login)
  ```
  `Config.report` is a trailing-optional field (`dict | None`), following the
  `gui:`/`strategy:` pattern. Env overrides (`REPORT_ENABLED`, `REPORT_TO`,
  `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`) win over config.

## 8. Acceptance criteria (how we know the step is done)

1. `build_report(...)` returns a dict matching the §7 schema exactly; a pure
   unit test asserts the full shape on a fixed `SeriesResult`+`Telemetry`+`Config`+`replay_path` (deterministic; `generated_at` stripped/fixed).
2. The report is **resizable** — a 3×3 / `num_games=2` fixture yields a
   correct smaller report (no 5×5 assumption).
3. `build_report` contains **no secrets** (no tokens, API keys, credential
   paths) — a test greps the serialized JSON.
4. `GmailSender.send` is covered by a test that **monkeypatches** the Gmail
   service (`build`/`users`/`messages`/`send`) and asserts: the `raw` field
   decodes to a message with `To` = recipient, `Subject` = subject,
   `Content-Type: application/json`, and the JSON body; **no real network call
   is made**; returns the stubbed message id.
5. **Gating:** with `enabled=false` OR token absent, `maybe_send_report` is a
   no-op (no `build` call, no send) and returns without raising — test asserts
   the gmail service is never constructed.
6. `maybe_send_report` is **fail-soft**: if `send` raises, the exception is
   caught and logged; the orchestrator still prints the series result (test
   injects a raising sender and asserts no propagation).
7. The orchestrator `__main__.py` calls `maybe_send_report(result, telemetry.summary(), config, replay_log.path)` after the series, and the 165 prior tests still pass (no new failures, no real send).
8. `config.yaml` + `Config.report` carry the §7 `report:` block; env
   overrides take precedence — test asserts `REPORT_ENABLED=true` flips the
   gate and `GMAIL_TOKEN_PATH` overrides the path.
9. **(Manual AC, deferred operator artifact)** Live send: with `enabled=true`
   + a valid `token.json` (from `python -m src.reporting auth`), a real series
   run sends the JSON body to `rmisegal+uoh26b@gmail.com`; the sent message id
   is logged. Recorded in the README "Email reporting" section with the
   one-time OAuth login steps. Not executed in CI (no real credentials).
10. `.gitignore` ignores `secrets/`, `gmail_credentials.json`,
    `gmail_token.json`; `.env.example` documents the four env overrides;
    `config.yaml` contains no real secrets.
11. `src/reporting/` files are ruff-clean, ≤150 lines each, and the new
    package's test coverage is ≥85% (matching the Step 6 coverage gate).
12. New deps added to the `dev` group in `pyproject.toml` (`google-auth`,
    `google-auth-oauthlib`, `google-api-python-client`); `uv lock` updated.

## 9. Resolved questions / open items

- **Q: SMTP or Gmail API?** → **A:** Gmail API (Director). The step name
  demands it; SMTP rejected.
- **Q: How rich is the report?** → **A:** Rich-but-compact (Director). Header
  + per-sub-game + totals + telemetry + replay filename; no inline JSONL.
- **Q: When does the orchestrator send?** → **A:** Always-on when credentialed
  (Director). Safety net = `enabled` default `false` + absent token.
- **Q: Attach the JSONL?** → **A:** No (Director). Reference filename only;
  assignment says JSON body only.
- **Q: Sender address?** → **A:** The Gmail API can only send as the
  authenticated OAuth account, so the sender is whatever account did the
  one-time login. `report.to` (the lecturer) is the recipient. No `from` in
  config — it's implicit in the OAuth identity.
- **Q: Service account?** → **A:** Rejected — can't reach personal `@gmail.com`.
- **Still open (note for Builder):** verify the live Gmail API v1
  `messages().send` `raw` base64url shape + the `google-auth-oauthlib`
  `InstalledAppFlow`/`local_server` token-cache shape via context7 before
  writing the TODO. The `google-api-python-client` `build('gmail','v1',...)`
  v1 discovery may be deprecated in favor of the new generated client —
  Builder picks whichever context7 confirms as current and documents it in an
  `SDK_REFERENCE_gmail.md`.

## 10. Notes for the Builder session

- **Verify the live SDK first** (context7) — same discipline as Steps 5/6/7.
  Confirm: `google.oauth2.credentials.Credentials`, `google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(...).run_local_server(scopes=[...])`, `googleapiclient.discovery.build('gmail','v1',credentials=...)`, `gmail.users().messages().send(userId='me', body={'raw': <base64url>}).execute()`, and the `creds.to_json()`/`Credentials.from_authorized_user_info` token-cache round-trip. Write `SDK_REFERENCE_gmail.md`.
- **Fat TODO, atomic boxes** — follow the Step 5/6/7 TODO style (named
  phases A–E, copy-paste code for `report.py` + `gmail_client.py`, per-box
  check). The pure `build_report` and the gating logic deserve the most detail
  (they carry the test-suite-safety guarantee).
- **Determinism in tests** — `build_report` must accept an injected
  `now`/`generated_at` (or the test strips it) so the snapshot is stable.
- **Fail-soft is load-bearing** — `maybe_send_report` must never raise into
  the orchestrator; a broken/missing token or a Gmail API error is logged and
  swallowed so a reporting failure can never mask a good series result.
- **No hard-coding** — the lecturer address is the `config.yaml` default for
  `report.to`, never a literal in `gmail_client.py`/`report.py`.
- **Cyber hygiene** — `.gitignore` must add `secrets/`,
  `gmail_credentials.json`, `gmail_token.json` before any credential file can
  exist; `.env.example` documents the four env overrides; never log the
  `raw`/token.
- **Coverage gate** — keep `src/reporting/` files ≤150 lines and ≥85% covered
  (Step 6 precedent); the live send path is the only uncovered line and is
  marked `# pragma: no cover` (manual AC9).
