# PRD — Step 8: Gmail API Reporting

- **Status:** triplet-built
- **Source:** `DECISION_step8_gmail_api.md`; SDK ground truth: `SDK_REFERENCE_gmail.md`
- **Assignment references:** §13 Table 4 (step 8 = Gmail API reporting, engineering
  priority order); §report email target `rmisegal+uoh26b@gmail.com` (JSON body only);
  §6 hard constraints (no hard-coding; JSON-only email report at end of a 6-sub-game
  series).

---

## 1. Problem & context

After a 6-sub-game series finishes, the orchestrator (`src/orchestrator/__main__.py`)
currently only prints a summary to stdout. The assignment requires a **JSON-only email
report** of the series result sent to the fixed lecturer address via the **Gmail API** —
the step is literally named "Gmail API", so SMTP is out, and personal `@gmail.com`
destinations rule out service accounts, leaving **OAuth2 user-consent** as the only viable
path.

Step 8 adds a `src/reporting/` client-tier package: a pure JSON report builder, a Gmail
API v1 sender (`users().messages().send` with the `raw` base64url MIME), a one-time OAuth
login CLI, and a `maybe_send_report(...)` hook wired into the orchestrator after the
series. Sending is **always-on when credentialed**, but defaults to **disabled** in config
and is a **no-op without a refresh token**, so the existing 165-test suite stays green and
no dev run accidentally mails the lecturer. The actual live send is a deferred manual
operator step (one-time browser OAuth + a real series run), matching the Step 5 live-LLM,
Step 6 screenshot, and Step 7 gcloud deploy conventions.

---

## 2. Goal & success metric

After this step, the project has:

1. A pure, deterministic `build_report(...)` that turns a `SeriesResult` + telemetry
   summary + `Config` + replay-log path into the §7 JSON report shape — no network, no
   secrets.
2. A `GmailSender` that base64url-encodes `To`/`Subject`/`Content-Type: application/json`
   + the JSON body into a `raw` message and calls `gmail.users().messages().send(...)`,
   returning the sent message id — offline-testable by monkeypatching the service.
3. A one-time OAuth login CLI (`python -m src.reporting auth`) that writes a refresh
   `token.json` from a downloaded `credentials.json`.
4. A `maybe_send_report(...)` hook in the orchestrator that sends **iff**
   `config.report['enabled'] is True` **AND** the token file exists, is **fail-soft**
   (never raises into the orchestrator), and is a no-op by default so all 165 existing
   tests stay green.
5. The 12 acceptance criteria below satisfied; the live send (AC9) is a manual operator
   artifact.

---

## 3. Stories

- As the **orchestrator**, after `run_series` returns and the telemetry summary is
  computed, I need `maybe_send_report(result, telemetry.summary(), config,
  replay_log.path)` to be called so a report can be sent without changing the series flow.
- As the **report builder**, I need a pure `build_report(...)` so the report shape is
  unit-testable offline with a fixed clock and no secrets.
- As the **Gmail sender**, I need to wrap `users().messages().send` so the JSON report is
  the email body (`Content-Type: application/json`), never an attachment.
- As the **operator**, I need a one-time `python -m src.reporting auth` CLI to produce a
  refresh `token.json` so the live send (AC9) works without re-consenting each run.
- As the **CI pipeline**, I need every reporting test to run offline (no real
  `credentials.json`, no network, no token) so the gate stays green on every push.
- As the **grader**, I need a README "Email reporting" section documenting the one-time
  OAuth login and the live send proof (sent message id logged).

---

## 4. Functional requirements

- **FR1 — Pure report builder.** `build_report(series_result, telemetry, config,
  replay_path, *, a_was_cop_per_subgame, now=None) -> dict` returns the DECISION §7 JSON
  shape: `schema_version`, `generated_at`, `config`, `agents`, `series` (with per-sub-game
  `a_was_cop`), `telemetry`, `replay_log`. No I/O, no network, no secrets. `now` is
  injectable for deterministic tests.
- **FR2 — Resizable report.** The builder makes no 5×5 / `num_games=6` assumption; a 3×3
  / `num_games=2` fixture yields a correct smaller report.
- **FR3 — No secrets in body.** The serialized report contains no tokens, API keys, or
  credential paths. Verified by a grep test.
- **FR4 — GmailSender.** `GmailSender(credentials_path, token_path).__init__`;
  `send(to, subject, body: dict) -> str` base64url-encodes an RFC2822 message with headers
  `To`, `Subject`, `Content-Type: application/json` and the JSON body, calls
  `gmail.users().messages().send(userId='me', body={'raw': ...}).execute()`, returns the
  sent message `id`. Uses `base64.urlsafe_b64encode` (url-safe, padding retained — see SDK
  ref §1.2).
- **FR5 — OAuth login CLI.** `python -m src.reporting auth` runs
  `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)` (scope
  `gmail.send`) and writes `token.json` via `creds.to_json()`. Manual operator step; not
  in CI.
- **FR6 — Gated orchestrator hook.** `maybe_send_report(series_result, telemetry, config,
  replay_path) -> None` sends **iff** `config.report['enabled'] is True` **AND** the token
  file exists at the resolved path; otherwise no-op (the gmail service is never
  constructed). Default `enabled: false`, no token in the test env ⇒ all 165 tests stay
  green. Resolved token path = env `GMAIL_TOKEN_PATH` else `config.report['token_path']`
  else default `secrets/gmail_token.json`.
- **FR7 — Fail-soft.** `maybe_send_report` never raises into the orchestrator: any
  `send`/auth/refresh error is caught and logged; the series result still prints.
- **FR8 — Config block.** A trailing-optional `report:` block in `config.yaml`
  (`enabled`, `to`, `subject`, `credentials_path`, `token_path`) + a `Config.report:
  dict | None` field, following the `gui:`/`strategy:` pattern. Env overrides
  (`REPORT_ENABLED`, `REPORT_TO`, `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`) win over
  config.
- **FR9 — Cyber hygiene.** `.gitignore` ignores `secrets/`, `gmail_credentials.json`,
  `gmail_token.json`; `.env.example` documents the four env overrides; `config.yaml`
  contains no real secrets; the report body contains no secrets; OAuth scope is the
  minimal `gmail.send`.
- **FR10 — Offline-testable.** New tests in `tests/test_reporting/` cover: the pure
  builder shape + resize + no-secrets; a monkeypatched Gmail send (decodes `raw`, asserts
  headers + body, no network, returns stubbed id); gating no-op when `enabled=false` or
  token absent; fail-soft on raising sender; env-override precedence. All run without any
  real credentials or network.
- **FR11 — No hard-coding.** The lecturer address is the `config.yaml` default for
  `report.to`, never a literal in `report.py`/`gmail_client.py`/`auth.py`.
- **FR12 — Deps.** `google-auth`, `google-auth-oauthlib`, `google-api-python-client` added
  to the `dev` group in `pyproject.toml`; `uv lock` updated.

---

## 5. Non-functional requirements

- **NFR1 — Config-driven:** all recipient/subject/paths come from `config.yaml` or env;
  no path/address/subject literal in source.
- **NFR2 — Resizable:** the builder reads `grid_size`/`num_games` from config; no fixed
  grid assumption anywhere.
- **NFR3 — Backward compatibility (CRITICAL):** the 165 existing tests and local runs
  must keep passing with no token and `enabled: false`. Reporting is strictly additive,
  gated, fail-soft.
- **NFR4 — Cyber hygiene:** Google credentials live on disk only (git-ignored), never in
  `config.yaml`/git/logs; minimal `gmail.send` scope; the `raw`/token is never logged.
- **NFR5 — Segal gate:** ruff clean; every `src/reporting/` file ≤ 150 lines; the new
  package's test coverage ≥ 85% (Step 6 precedent); the live send path is the only
  uncovered line and is marked `# pragma: no cover` (manual AC9).
- **NFR6 — uv-only:** all dependency changes via `uv`; do not hand-edit `requirements.txt`.

---

## 6. In scope / Out of scope

**In scope:**
- `src/reporting/` package (`report.py`, `gmail_client.py`, `auth.py`, `__main__.py`,
  `__init__.py`).
- The `report:` config block + `Config.report` field + env overrides.
- The `maybe_send_report` orchestrator hook (gated, fail-soft).
- `.gitignore` + `.env.example` credential entries.
- `tests/test_reporting/` (`test_report.py`, `test_gmail_client.py`, `test_gating.py`).
- New dev deps in `pyproject.toml` + `uv lock`.

**Out of scope (deferred):**
- The **live send** to the real lecturer address → deferred manual operator artifact
  (AC9), like Step 5/6/7 manual artifacts.
- Inlining the full per-ply JSONL into the body → the JSONL is a separate file deliverable;
  only its filename is referenced in the report.
- Attaching the JSONL as a MIME attachment → rejected: assignment says "JSON body only".
- Inter-group bonus competition JSON report → separate optional ROADMAP deliverable.

---

## 7. Acceptance criteria

<!-- Carried over verbatim from DECISION §8; numbered 1–12; AC9 is manual. -->

1. **[AC1 — Report shape]** `build_report(...)` returns a dict matching the DECISION §7
   schema exactly; a pure unit test asserts the full shape on a fixed
   `SeriesResult`+`Telemetry`+`Config`+`replay_path` (deterministic; `generated_at`
   stripped/fixed via the injectable `now`). Verified by `tests/test_reporting/test_report.py`.
2. **[AC2 — Resizable]** A 3×3 / `num_games=2` fixture yields a correct smaller report (no
   5×5 assumption). Verified by a second builder test.
3. **[AC3 — No secrets in body]** `build_report` contains no tokens, API keys, or
   credential paths — a test greps the serialized JSON. Verified by `test_report.py`.
4. **[AC4 — GmailSender send, stubbed]** `GmailSender.send` is covered by a test that
   monkeypatches the Gmail service (`build`/`users`/`messages`/`send`) and asserts: the
   `raw` field decodes to a message with `To` = recipient, `Subject` = subject,
   `Content-Type: application/json`, and the JSON body; **no real network call**; returns
   the stubbed message id. Verified by `tests/test_reporting/test_gmail_client.py`.
5. **[AC5 — Gating no-op]** With `enabled=false` OR token absent, `maybe_send_report` is a
   no-op (no `build` call, no send) and returns without raising — the test asserts the
   gmail service is never constructed. Verified by `tests/test_reporting/test_gating.py`.
6. **[AC6 — Fail-soft]** If `send` raises, the exception is caught and logged; the
   orchestrator still prints the series result — a test injects a raising sender and
   asserts no propagation. Verified by `test_gating.py`.
7. **[AC7 — Orchestrator hook + suite compat]** The orchestrator `__main__.py` calls
   `maybe_send_report(result, telemetry.summary(), config, replay_log.path)` after the
   series, and the 165 prior tests still pass (no new failures, no real send). Verified by
   the full `uv run pytest -q` run.
8. **[AC8 — Config + env overrides]** `config.yaml` + `Config.report` carry the §7
   `report:` block; env overrides take precedence — a test asserts `REPORT_ENABLED=true`
   flips the gate and `GMAIL_TOKEN_PATH` overrides the path. Verified by `test_gating.py`.
9. **[AC9 — MANUAL: live send]** (Operator step — not automated.) With `enabled=true` +
   a valid `token.json` (from `python -m src.reporting auth`), a real series run sends the
   JSON body to `rmisegal+uoh26b@gmail.com`; the sent message id is logged. Recorded in
   the README "Email reporting" section with the one-time OAuth login steps. Not executed
   in CI (no real credentials).
10. **[AC10 — Hygiene artifacts]** `.gitignore` ignores `secrets/`, `gmail_credentials.json`,
    `gmail_token.json`; `.env.example` documents the four env overrides; `config.yaml`
    contains no real secrets. Verified by a static-guard test.
11. **[AC11 — Segal gate]** `src/reporting/` files are ruff-clean, ≤ 150 lines each, and
    the new package's test coverage is ≥ 85% (matching the Step 6 coverage gate). Verified
    by `ruff check` + `pytest --cov --cov-fail-under=85` + a line-count guard.
12. **[AC12 — Deps]** New deps added to the `dev` group in `pyproject.toml`
    (`google-auth`, `google-auth-oauthlib`, `google-api-python-client`); `uv lock` updated.
    Verified by `pyproject.toml` + `uv.lock` inspection.

---

## 8. Dependencies

- **Upstream (needs):**
  - Step 3: `SeriesResult` / `SubGameResult` (`src/game/engine.py`), `Telemetry.summary()`
    (`src/orchestrator/recorders.py`), `ReplayLog.path`, the orchestrator `__main__` flow.
  - Step 2/3: `Config`, `load_config`, the trailing-optional `gui:`/`strategy:` pattern
    (`src/game/config.py`).
  - SDK reference: `SDK_REFERENCE_gmail.md` (verified Gmail API + google-auth-oauthlib shapes).
- **Downstream (unblocks):**
  - None — this is the final step (step 8 of 8). The report JSON schema is the project's
    terminal deliverable shape.
  - README: the "Email reporting" section + the live-send proof are the main README artifact.

---

## 9. Acceptance-coverage view

| Acceptance criterion | Primary evidence | Secondary evidence |
|----------------------|------------------|--------------------|
| AC1 Report shape | `tests/test_reporting/test_report.py` (full-shape snapshot) | SDK ref §1 + DECISION §7 |
| AC2 Resizable | `test_report.py` (3×3 / num_games=2 fixture) | builder reads config |
| AC3 No secrets in body | `test_report.py` (grep guard) | NFR4 |
| AC4 GmailSender stubbed send | `test_gmail_client.py` (monkeypatched service) | SDK ref §1.2 |
| AC5 Gating no-op | `test_gating.py` (service never constructed) | FR6/FR7 |
| AC6 Fail-soft | `test_gating.py` (raising sender, no propagation) | FR7 |
| AC7 Orchestrator hook + suite | `src/orchestrator/__main__.py` edit + `uv run pytest -q` ≥ 165 pass | PLAN §5 |
| AC8 Config + env overrides | `test_gating.py` (env precedence) | `config.yaml` + `Config.report` |
| AC9 Live send (MANUAL) | README "Email reporting" + sent message id log | `python -m src.reporting auth` |
| AC10 Hygiene artifacts | `test_gating.py` static guards | `.gitignore` + `.env.example` |
| AC11 Segal gate | `ruff check` + coverage ≥85% + ≤150-line guard | NFR5 |
| AC12 Deps | `pyproject.toml` + `uv.lock` inspection | `uv add --dev` |

---

## 10. References

- `docs/step8_gmail_api/DECISION_step8_gmail_api.md`
- `docs/step8_gmail_api/SDK_REFERENCE_gmail.md`
- `docs/_system/WORKFLOW.md`
- `src/game/engine.py` — `SubGameResult`, `SeriesResult`
- `src/orchestrator/recorders.py` — `Telemetry.summary()`, `ReplayLog.path`
- `src/orchestrator/__main__.py` — series flow + where the hook is wired
- `src/game/config.py` — `Config`, `load_config`, trailing-optional pattern
- `config.yaml` — `report:` block (new)
- Assignment §13 Table 4 (step 8); §6 hard constraints; report email target
