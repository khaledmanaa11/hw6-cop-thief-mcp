# TODO — Step 8: Gmail API Reporting

> Implements `PRD_step8_gmail_api.md` + `PLAN_step8_gmail_api.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**
> This is the Developer-session checklist. The Builder session that wrote this file
> did not edit source code.

## Rules for the Developer (read once, obey always)

1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never hard-code** the lecturer address, subject, or credential/token paths — read them
   from `config.yaml` (`report:` block) or env overrides. The address
   `rmisegal+uoh26b@gmail.com` appears ONLY in `config.yaml` as `report.to`, never in `src/`.
4. The 165 existing tests MUST keep passing. The hook is gated on
   `config.report['enabled'] is True` **AND** the token file existing. Default
   `enabled: false`; no token in CI ⇒ no-op. Reporting is strictly additive.
5. `maybe_send_report` MUST be **fail-soft**: wrap the whole send in `try/except Exception`
   that logs and swallows. A reporting failure must never crash the series output.
6. Every Gmail API shape in this TODO was verified against the live official Google docs
   (see `SDK_REFERENCE_gmail.md`): `build("gmail","v1",credentials=...)`,
   `service.users().messages().send(userId="me", body={"raw": <base64url>}).execute()`
   returns `{"id": ...}`; `base64.urlsafe_b64encode(...).decode()` (padding retained);
   `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)` → `Credentials`;
   `creds.to_json()` / `Credentials.from_authorized_user_info(info, scopes)`; refresh via
   `creds.refresh(Request())`. Copy the code exactly.
7. Keep every `src/reporting/` file ≤ 150 lines. Live OAuth/send paths get `# pragma: no cover`.
8. Use `uv` for dependency changes (`uv add --dev ...` then `uv lock`). Do not hand-edit `requirements.txt`.
9. Run commands from the repository root (the folder containing `config.yaml`).

## Conventions

- Language/runtime: Python 3.11+ using `uv`, pytest, `asyncio_mode=auto`.
- SDK reference: `docs/step8_gmail_api/SDK_REFERENCE_gmail.md`.
- The `raw` field: `base64.urlsafe_b64encode(message.as_bytes()).decode()` — url-safe,
  **padding retained** (the Gmail API accepts it; the official sample does not strip padding).
- Scope: `https://www.googleapis.com/auth/gmail.send` (minimal — send only).
- Each box format: **ID · file · action · detail · Check.**

---

## Phase A — deps, config block, hygiene

- [ ] **A1** — `pyproject.toml` — edit — add the three Google deps to the `[dependency-groups].dev`
      list (after the existing entries, before the closing `]`):
      ```toml
      "google-auth>=2.40",
      "google-auth-oauthlib>=1.2",
      "google-api-python-client>=2.150",
      ```
      Then run `uv sync` and `uv lock` so `uv.lock` is updated.
      **Check:** `uv run python -c "import googleapiclient, google.oauth2, google_auth_oauthlib; print('ok')"` prints `ok`.

- [ ] **A2** — `config.yaml` — edit — append the `report:` block at the end of the file
      (after the `gui:` block). These are the defaults; `enabled: false` keeps the suite green:
      ```yaml
      report:
        enabled: false        # flip to true + run `python -m src.reporting auth` once for the live send
        to: "rmisegal+uoh26b@gmail.com"
        subject: "HW6 Cop&Thief MCP series report"
        credentials_path: "secrets/gmail_credentials.json"   # OAuth client secret (Google Cloud Console)
        token_path: "secrets/gmail_token.json"               # refresh token (one-time login)
      ```
      **Check:** `uv run python -c "import yaml; d=yaml.safe_load(open('config.yaml')); r=d['report']; assert r['enabled'] is False; assert r['to']=='rmisegal+uoh26b@gmail.com'; assert r['credentials_path']=='secrets/gmail_credentials.json'; print('ok')"` prints `ok`.

- [ ] **A3** — `src/game/config.py` — edit — add a `_DEFAULT_REPORT` dict near the other
      `_DEFAULT_*` dicts (after `_DEFAULT_GUI`):
      ```python
      _DEFAULT_REPORT = {
          "enabled": False,
          "to": "rmisegal+uoh26b@gmail.com",
          "subject": "HW6 Cop&Thief MCP series report",
          "credentials_path": "secrets/gmail_credentials.json",
          "token_path": "secrets/gmail_token.json",
      }
      ```

- [ ] **A4** — `src/game/config.py` — edit — add the trailing-optional `report` field to the
      `Config` dataclass (after `gui: dict | None = None`):
      ```python
      report: dict | None = None
      ```

- [ ] **A5** — `src/game/config.py` — edit — wire the `report` block into `load_config`.
      Where the other trailing-optional blocks are resolved (the section that builds
      `agents`/`observation`/`gui`), add:
      ```python
      report = _merged_defaults(_DEFAULT_REPORT, data.get("report"))
      # env overrides win over config
      if os.environ.get("REPORT_ENABLED") is not None:
          report["enabled"] = os.environ["REPORT_ENABLED"].lower() == "true"
      if os.environ.get("REPORT_TO"):
          report["to"] = os.environ["REPORT_TO"]
      if os.environ.get("GMAIL_CREDENTIALS_PATH"):
          report["credentials_path"] = os.environ["GMAIL_CREDENTIALS_PATH"]
      if os.environ.get("GMAIL_TOKEN_PATH"):
          report["token_path"] = os.environ["GMAIL_TOKEN_PATH"]
      ```
      Then pass `report=report` into the `Config(...)` constructor call. (If `load_config`
      constructs `Config` positionally, add `report` as a keyword arg at the end — it is
      trailing-optional so existing callsites that omit it still work.) Also ensure
      `import os` is at the top of the file (add it if missing).
      **Check:** `uv run python -c "from src.game.config import load_config; c=load_config('config.yaml'); assert c.report['enabled'] is False; assert c.report['to']=='rmisegal+uoh26b@gmail.com'; print('ok')"` prints `ok`.

- [ ] **A6** — `src/game/config.py` — verify env override — confirm `REPORT_ENABLED=true`
      flips the gate at the config layer:
      ```powershell
      uv run python -c "
      import os
      os.environ['REPORT_ENABLED'] = 'true'
      os.environ['GMAIL_TOKEN_PATH'] = '/tmp/fake.json'
      from src.game.config import load_config
      c = load_config('config.yaml')
      assert c.report['enabled'] is True
      assert c.report['token_path'] == '/tmp/fake.json'
      print('ok')
      "
      ```
      **Check:** the command prints `ok`.

- [ ] **A7** — `.gitignore` — edit — add Google-credential entries (one per line, after the
      existing `runs/` line). Do not remove any existing entry:
      ```
      secrets/
      gmail_credentials.json
      gmail_token.json
      ```
      **Check:** `uv run python -c "t=open('.gitignore').read(); assert 'secrets/' in t; assert 'gmail_credentials.json' in t; assert 'gmail_token.json' in t; print('ok')"` prints `ok`.

- [ ] **A8** — `.env.example` — edit — append the Step 8 env contract at the end of the file
      (after the existing Step 7 client-side block):
      ```
      # --- Email reporting (Step 8) — set to enable the Gmail API report send ---
      # REPORT_ENABLED=false                 # flip to true to enable the report hook
      # REPORT_TO=rmisegal+uoh26b@gmail.com  # recipient (defaults to config.yaml report.to)
      # GMAIL_CREDENTIALS_PATH=secrets/gmail_credentials.json   # OAuth client secret path
      # GMAIL_TOKEN_PATH=secrets/gmail_token.json              # refresh token path (one-time login)
      ```
      **Check:** `uv run python -c "t=open('.env.example').read(); assert 'REPORT_ENABLED' in t; assert 'GMAIL_TOKEN_PATH' in t; print('ok')"` prints `ok`.

---

## Phase B — `src/reporting/report.py` (pure builder)

> Pure, deterministic, no I/O, no network, no secrets. `now` is injectable for tests.
> Line budget: ≤ 150 lines.

- [ ] **B1** — `src/reporting/__init__.py` — create — empty package marker:
      ```python
      """Step 8 — Gmail API reporting: pure report builder + GmailSender + OAuth login."""
      ```
      **Check:** `uv run python -c "import src.reporting; print('ok')"` prints `ok`.

- [ ] **B2** — `src/reporting/report.py` — create — add the module docstring and imports:
      ```python
      """Pure JSON report builder for the Gmail reporting step.

      Builds a rich-but-compact JSON dict from a SeriesResult + telemetry summary + Config
      + replay-log path, per DECISION_step8 §7. No I/O, no network, no secrets.
      `now` is injectable so tests get a deterministic `generated_at`.
      """
      from __future__ import annotations

      from datetime import datetime, timezone

      from src.game.config import Config
      from src.game.engine import SeriesResult
      ```
      **Check:** `uv run python -m py_compile src/reporting/report.py` succeeds.

- [ ] **B3** — `src/reporting/report.py` — edit — add `build_report`. This is the full pure
      builder; copy it verbatim. It reads only non-secret config fields and the passed
      telemetry dict; it never touches token/credential paths:
      ```python
      def build_report(
          series_result: SeriesResult,
          telemetry: dict,
          config: Config,
          replay_path: str,
          *,
          a_was_cop_per_subgame: list[bool],
          now: datetime | None = None,
      ) -> dict:
          """Return the report dict per DECISION §7 schema.

          Pure: no I/O, no network. `now` is injectable for deterministic tests; when
          omitted, uses datetime.now(timezone.utc). No secrets appear anywhere — this
          function never reads credentials_path/token_path/tokens.
          """
          generated_at = (now or datetime.now(timezone.utc)).isoformat()

          sub_games = []
          for idx, sg in enumerate(series_result.sub_games, 1):
              if idx - 1 < len(a_was_cop_per_subgame):
                  a_was_cop = bool(a_was_cop_per_subgame[idx - 1])
              else:
                  a_was_cop = sg.cop_group == "A"
              sub_games.append(
                  {
                      "index": idx,
                      "winner": sg.winner,
                      "cop_score": sg.cop_score,
                      "thief_score": sg.thief_score,
                      "moves_used": sg.moves_used,
                      "a_was_cop": a_was_cop,
                  }
              )

          agents = config.agents or {}
          llm_cfg = agents.get("llm") or {}
          observation = config.observation or {}
          scoring = config.scoring
          return {
              "schema_version": 1,
              "generated_at": generated_at,
              "config": {
                  "grid_size": list(config.grid_size),
                  "num_games": config.num_games,
                  "max_moves": config.max_moves,
                  "max_barriers": config.max_barriers,
                  "scoring": {
                      "cop_win": scoring.cop_win,
                      "thief_win": scoring.thief_win,
                      "cop_loss": scoring.cop_loss,
                      "thief_loss": scoring.thief_loss,
                  },
              },
              "agents": {
                  "cop": agents.get("cop"),
                  "thief": agents.get("thief"),
                  "llm_model": llm_cfg.get("model"),
                  "observation_mode": observation.get("mode"),
              },
              "series": {
                  "group_a_total": series_result.group_a_total,
                  "group_b_total": series_result.group_b_total,
                  "sub_games": sub_games,
              },
              "telemetry": telemetry,
              "replay_log": replay_path,
          }
      ```
      **Check:** `uv run python -c "from src.reporting.report import build_report; print(callable(build_report))"` prints `True`.

- [ ] **B4** — `src/reporting/report.py` — audit — confirm ≤ 150 lines and no secret-shaped
      strings:
      ```powershell
      uv run python -c "
      from pathlib import Path
      t = Path('src/reporting/report.py').read_text(encoding='utf-8')
      assert len(t.splitlines()) <= 150, len(t.splitlines())
      bad = [x for x in ['token', 'credential', 'api_key', 'secret'] if x.lower() in t.lower()]
      assert not bad, bad
      print('ok')
      "
      ```
      **Check:** the command prints `ok`. (The word "token" should not appear in this file at all.)

---

## Phase C — `src/reporting/auth.py` + `src/reporting/gmail_client.py`

> GmailSender wraps the confirmed `users().messages().send` path (SDK ref §1.2).
> `build_credentials` returns `None` when there is no token file (the gate). Both files ≤ 150 lines.

- [ ] **C1** — `src/reporting/auth.py` — create — add the module docstring, scope constant,
      and imports:
      ```python
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
      ```
      **Check:** `uv run python -m py_compile src/reporting/auth.py` succeeds.

- [ ] **C2** — `src/reporting/auth.py` — edit — add `build_credentials`. Returns `None` when
      the token file is absent (the gate's load-bearing no-op branch). Refreshes on expiry
      and re-persists:
      ```python
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
      ```
      **Check:** `uv run python -c "from src.reporting.auth import build_credentials; print(callable(build_credentials))"` prints `True`.

- [ ] **C3** — `src/reporting/auth.py` — edit — add `cmd_auth` (the one-time OAuth login).
      This is a manual operator path; mark it `# pragma: no cover`:
      ```python
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
      ```
      **Check:** `uv run python -m py_compile src/reporting/auth.py` succeeds.

- [ ] **C4** — `src/reporting/auth.py` — audit — confirm ≤ 150 lines and no `src.game` /
      `src.orchestrator` imports (keep this module dependency-light):
      ```powershell
      uv run python -c "
      from pathlib import Path
      t = Path('src/reporting/auth.py').read_text(encoding='utf-8')
      assert len(t.splitlines()) <= 150, len(t.splitlines())
      bad = [x for x in ['src.game', 'src.orchestrator', 'src.strategy', 'src.agents'] if x in t]
      assert not bad, bad
      print('ok')
      "
      ```
      **Check:** the command prints `ok`.

- [ ] **C5** — `src/reporting/gmail_client.py` — create — add the module docstring and imports:
      ```python
      """GmailSender + the orchestrator's fail-soft maybe_send_report hook.

      GmailSender wraps the confirmed Gmail API v1 send path (SDK_REFERENCE_gmail §1):
      base64.urlsafe_b64encode of an RFC2822 EmailMessage with To/Subject/
      Content-Type: application/json headers and the JSON body, then
      service.users().messages().send(userId='me', body={'raw': ...}).execute().
      """
      from __future__ import annotations

      import base64
      import json
      from email.message import EmailMessage

      from src.reporting.auth import SCOPES, build_credentials
      from src.reporting.report import build_report
      ```
      **Check:** `uv run python -m py_compile src/reporting/gmail_client.py` succeeds.

- [ ] **C6** — `src/reporting/gmail_client.py` — edit — add the `GmailSender` class. The
      `send` method builds the `raw` MIME exactly per SDK ref §1.2 (url-safe base64,
      padding retained) and returns the sent message id:
      ```python
      class GmailSender:
          """Wraps gmail.users().messages().send for a JSON-only email body.

          `to`/`subject` come from config (report.to / report.subject) — never literals.
          The sender is the authenticated OAuth account (implicit `from`).
          """

          def __init__(self, credentials_path: str, token_path: str) -> None:
              self._credentials_path = credentials_path
              self._token_path = token_path
              self._scopes = SCOPES

          def send(self, to: str, subject: str, body: dict) -> str:
              """Send `body` (a dict) as the JSON email body; return the sent message id.

              Raises if the token is missing/invalid — the caller (maybe_send_report)
              catches and logs (fail-soft).
              """
              from googleapiclient.discovery import build

              creds = build_credentials(
                  self._credentials_path, self._token_path, scopes=self._scopes
              )
              if creds is None:
                  raise FileNotFoundError(
                      f"Gmail token not found at {self._token_path}; "
                      "run `python -m src.reporting auth` first."
                  )

              message = EmailMessage()
              message.set_content(json.dumps(body))
              message["To"] = to
              message["Subject"] = subject
              message["Content-Type"] = "application/json"

              # CONFIRMED (SDK ref §1.2): url-safe base64, padding retained.
              raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
              service = build("gmail", "v1", credentials=creds)
              sent = (
                  service.users()
                  .messages()
                  .send(userId="me", body={"raw": raw})
                  .execute()
              )
              return sent["id"]
      ```
      **Check:** `uv run python -c "from src.reporting.gmail_client import GmailSender; print(callable(GmailSender))"` prints `True`.

- [ ] **C7** — `src/reporting/gmail_client.py` — edit — add the `maybe_send_report` hook.
      This is the load-bearing gate + fail-soft wrapper. It sends **iff**
      `config.report['enabled'] is True` **AND** the token file exists; otherwise no-op
      without constructing the gmail service. It never raises into the orchestrator:
      ```python
      def maybe_send_report(series_result, telemetry, config, replay_path) -> None:
          """Gated, fail-soft report hook for the orchestrator.

          Sends iff config.report['enabled'] is True AND the token file exists at the
          resolved path. Default enabled=False + no token in CI -> no-op, so the 165
          prior tests stay green. Never raises into the orchestrator (fail-soft).
          """
          import os

          report = config.report or {}
          if not report.get("enabled"):
              return  # gate: disabled by default

          token_path = report.get("token_path", "secrets/gmail_token.json")
          if not os.path.exists(token_path):
              return  # gate: no token -> no-op (do not even build the service)

          try:
              a_was_cop = [sg.cop_group == "A" for sg in series_result.sub_games]
              body = build_report(
                  series_result, telemetry, config, replay_path,
                  a_was_cop_per_subgame=a_was_cop,
              )
              sender = GmailSender(
                  report.get("credentials_path", "secrets/gmail_credentials.json"),
                  token_path,
              )
              msg_id = sender.send(report.get("to", ""), report.get("subject", ""), body)
              print(f"Report sent: message id {msg_id}")
          except Exception as exc:  # noqa: BLE001 — fail-soft: never crash the series
              print(f"Report send failed (non-fatal): {exc}")
      ```
      **Check:** `uv run python -c "from src.reporting.gmail_client import maybe_send_report; print(callable(maybe_send_report))"` prints `True`.

- [ ] **C8** — `src/reporting/gmail_client.py` — audit — confirm ≤ 150 lines and no
      hard-coded lecturer address:
      ```powershell
      uv run python -c "
      from pathlib import Path
      t = Path('src/reporting/gmail_client.py').read_text(encoding='utf-8')
      assert len(t.splitlines()) <= 150, len(t.splitlines())
      assert 'rmisegal' not in t, 'lecturer address must not be hard-coded in source'
      print('ok')
      "
      ```
      **Check:** the command prints `ok`.

- [ ] **C9** — no-token no-op smoke — with `enabled=False` and no token, the hook returns
      without constructing anything:
      ```powershell
      uv run python -c "
      import os
      os.environ.pop('REPORT_ENABLED', None)
      os.environ.pop('GMAIL_TOKEN_PATH', None)
      from src.game.config import load_config
      from src.reporting.gmail_client import maybe_send_report
      from src.game.engine import SeriesResult, SubGameResult
      c = load_config('config.yaml')
      res = SeriesResult(sub_games=[], group_a_total=0, group_b_total=0)
      maybe_send_report(res, {}, c, 'runs/x.jsonl')   # must not raise, must not print 'Report sent'
      print('ok')
      "
      ```
      **Check:** the command prints only `ok` (no `Report sent` line).

---

## Phase D — orchestrator hook wiring + reporting CLI

- [x] **D1** — `src/orchestrator/__main__.py` — edit — add the import at the top (after the
      existing `from src.orchestrator.recorders import ...` line):
      ```python
      from src.reporting.gmail_client import maybe_send_report
      ```
      **Check:** `uv run python -m py_compile src/orchestrator/__main__.py` succeeds.

- [x] **D2** — `src/orchestrator/__main__.py` — edit — wire the hook. After the existing
      `print(f"Replay log: {replay_log.path}")` line (the last line inside `async def main`,
      before `if __name__ == "__main__":`), add:
      ```python
      # Step 8: gated, fail-soft Gmail report hook. No-op unless config.report['enabled']
      # is True AND a token file exists (default disabled -> 165 prior tests stay green).
      maybe_send_report(result, s, config, replay_log.path)
      ```
      Do not change any other line. `s` is `telemetry.summary()` already computed above.
      **Check:** `uv run python -m py_compile src/orchestrator/__main__.py` succeeds AND
      `uv run python -c "import src.orchestrator.__main__; print('ok')"` prints `ok`.

- [x] **D3** — `src/reporting/__main__.py` — create — add the CLI for the operator. Both
      subcommands are manual operator tools (`# pragma: no cover`); tests do not exercise
      them. Line budget ≤ 150 lines:
      ```python
      """CLI for the reporting package: `python -m src.reporting auth|send`.

      `auth` — one-time OAuth login (writes token.json). Manual operator step (AC9).
      `send` — ad-hoc send for the operator. Both are pragma-no-cover (live paths).
      """
      from __future__ import annotations

      import sys

      from src.game.config import load_config
      from src.reporting.auth import SCOPES, cmd_auth


      def _resolve(config):
          report = config.report or {}
          return report


      def main() -> None:  # pragma: no cover — manual operator CLI
          config = load_config("config.yaml")
          report = _resolve(config)
          cmd = sys.argv[1] if len(sys.argv) > 1 else ""

          if cmd == "auth":
              cmd_auth(
                  report.get("credentials_path", "secrets/gmail_credentials.json"),
                  report.get("token_path", "secrets/gmail_token.json"),
                  scopes=SCOPES,
              )
          elif cmd == "send":
              print(
                  "Ad-hoc send is not wired in the CLI; run `python -m src.orchestrator` "
                  "with report.enabled=true to send a real series report."
              )
          else:
              print("usage: python -m src.reporting {auth|send}")


      if __name__ == "__main__":  # pragma: no cover
          main()
      ```
      **Check:** `uv run python -m py_compile src/reporting/__main__.py` succeeds AND
      `uv run python -m src.reporting` prints `usage: python -m src.reporting {auth|send}`.

- [x] **D4** — `src/orchestrator/__main__.py` — audit — confirm no lecturer address leaked
      in and the file still imports clean:
      ```powershell
      uv run python -c "
      from pathlib import Path
      t = Path('src/orchestrator/__main__.py').read_text(encoding='utf-8')
      assert 'rmisegal' not in t
      assert 'maybe_send_report' in t
      print('ok')
      "
      ```
      **Check:** the command prints `ok`.

---

## Phase E — tests (`tests/test_reporting/`)

> All offline: no real credentials, no network, no token. `asyncio_mode=auto` is set in
> pyproject — `async def test_...` runs directly with no decorator.

- [x] **E1** — `tests/test_reporting/__init__.py` — create — empty package marker:
      ```python
      ```
      **Check:** `uv run python -c "import tests.test_reporting; print('ok')"` prints `ok`.

- [x] **E2** — `tests/test_reporting/test_report.py` — create — add imports and a fixture
      builder for a fixed `SeriesResult`+`Config`+telemetry dict. The fixed `now` makes the
      snapshot deterministic:
      ```python
      """Pure-builder tests for src/reporting/report.py. No network, no secrets."""
      from datetime import datetime, timezone

      from src.game.config import Config, ScoringConfig
      from src.game.engine import SeriesResult, SubGameResult
      from src.reporting.report import build_report


      def _cfg(grid=(5, 5), num_games=6):
          return Config(
              grid_size=grid,
              max_moves=25,
              num_games=num_games,
              max_barriers=5,
              scoring=ScoringConfig(20, 10, 5, 5),
              agents={"cop": "llm", "thief": "llm", "llm": {"model": "claude-haiku-4-5-20251001"}},
              observation={"mode": "noisy"},
          )


      def _telemetry():
          return {
              "calls": 84, "avg_ms": 1.2, "p95_ms": 3.0,
              "boot_ping": {"cop_ms": 5.0, "thief_ms": 5.0},
              "llm_calls": 48, "llm_avg_ms": 600.0, "llm_input_tokens": 12000,
              "llm_output_tokens": 3000, "llm_estimated_cost_usd": 0.012,
          }


      FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
      ```
      **Check:** `uv run python -m py_compile tests/test_reporting/test_report.py` succeeds after E3+.

- [x] **E3** — `tests/test_reporting/test_report.py` — edit — add
      `test_build_report_full_shape` (AC1):
      ```python
      def test_build_report_full_shape():
          res = SeriesResult(
              sub_games=[SubGameResult("COP", 20, 5, 7, cop_group="A", thief_group="B")],
              group_a_total=30, group_b_total=30,
          )
          report = build_report(
              res, _telemetry(), _cfg(), "runs/20260627T120000Z.jsonl",
              a_was_cop_per_subgame=[True], now=FIXED_NOW,
          )
          assert report["schema_version"] == 1
          assert report["generated_at"] == FIXED_NOW.isoformat()
          assert report["config"] == {
              "grid_size": [5, 5], "num_games": 6, "max_moves": 25, "max_barriers": 5,
              "scoring": {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5},
          }
          assert report["agents"] == {
              "cop": "llm", "thief": "llm",
              "llm_model": "claude-haiku-4-5-20251001", "observation_mode": "noisy",
          }
          assert report["series"]["group_a_total"] == 30
          assert report["series"]["sub_games"][0] == {
              "index": 1, "winner": "COP", "cop_score": 20, "thief_score": 5,
              "moves_used": 7, "a_was_cop": True,
          }
          assert report["replay_log"] == "runs/20260627T120000Z.jsonl"
          assert report["telemetry"]["calls"] == 84
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_report.py::test_build_report_full_shape` passes.

- [x] **E4** — `tests/test_reporting/test_report.py` — edit — add
      `test_build_report_resizable_3x3` (AC2):
      ```python
      def test_build_report_resizable_3x3():
          res = SeriesResult(
              sub_games=[
                  SubGameResult("THIEF", 5, 10, 12, cop_group="B", thief_group="A"),
                  SubGameResult("COP", 20, 5, 9, cop_group="A", thief_group="B"),
              ],
              group_a_total=15, group_b_total=25,
          )
          report = build_report(
              res, _telemetry(), _cfg(grid=(3, 3), num_games=2), "runs/x.jsonl",
              a_was_cop_per_subgame=[False, True], now=FIXED_NOW,
          )
          assert report["config"]["grid_size"] == [3, 3]
          assert report["config"]["num_games"] == 2
          assert len(report["series"]["sub_games"]) == 2
          assert report["series"]["sub_games"][0]["a_was_cop"] is False
          assert report["series"]["sub_games"][1]["a_was_cop"] is True
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_report.py::test_build_report_resizable_3x3` passes.

- [x] **E5** — `tests/test_reporting/test_report.py` — edit — add
      `test_report_has_no_secrets` (AC3):
      ```python
      def test_report_has_no_secrets():
          import json
          res = SeriesResult(
              sub_games=[SubGameResult("COP", 20, 5, 7, "A", "B")],
              group_a_total=20, group_b_total=5,
          )
          report = build_report(
              res, _telemetry(), _cfg(), "runs/x.jsonl",
              a_was_cop_per_subgame=[True], now=FIXED_NOW,
          )
          blob = json.dumps(report).lower()
          for needle in ["token", "credential", "api_key", "secret", "password"]:
              assert needle not in blob, f"report contains {needle!r}"
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_report.py::test_report_has_no_secrets` passes.

- [x] **E6** — `tests/test_reporting/test_gmail_client.py` — create — add imports and a
      fake gmail service factory (AC4). Monkeypatch `discovery.build` and
      `build_credentials` so no network and no real credentials:
      ```python
      """Stubbed GmailSender.send test — no network, no real credentials (AC4)."""
      import base64
      import json
      from unittest.mock import patch

      from src.reporting.gmail_client import GmailSender


      class _StubMessages:
          def __init__(self, captured):
              self._captured = captured

          def send(self, userId, body):
              self._captured["userId"] = userId
              self._captured["raw"] = body["raw"]
              return self

          def execute(self):
              return {"id": "stub-msg-id", "threadId": "t1"}


      class _StubUsers:
          def __init__(self, captured):
              self._captured = captured

          def messages(self):
              return _StubMessages(self._captured)


      def _stub_service(captured):
          class _Service:
              def users(self):
                  return _StubUsers(captured)
          return _Service()
      ```
      **Check:** `uv run python -m py_compile tests/test_reporting/test_gmail_client.py` succeeds after E7+.

- [x] **E7** — `tests/test_reporting/test_gmail_client.py` — edit — add
      `test_send_stubbed_returns_id_and_raw` (AC4): patch `googleapiclient.discovery.build`
      to the stub service and `src.reporting.gmail_client.build_credentials` to a dummy
      creds; assert the returned id, and decode the `raw` to verify headers + body:
      ```python
      def test_send_stubbed_returns_id_and_raw():
          captured = {}
          body = {"schema_version": 1, "series": {"group_a_total": 30}}
          with patch("src.reporting.gmail_client.build_credentials", return_value=object()), \
               patch("googleapiclient.discovery.build", return_value=_stub_service(captured)):
              sender = GmailSender("secrets/c.json", "secrets/t.json")
              msg_id = sender.send("rmisegal+uoh26b@gmail.com", "HW6 report", body)
          assert msg_id == "stub-msg-id"
          assert captured["userId"] == "me"
          # decode the raw MIME and assert headers + JSON body
          raw = captured["raw"]
          mime = base64.urlsafe_b64decode(raw).decode("utf-8")
          assert "To: rmisegal+uoh26b@gmail.com" in mime
          assert "Subject: HW6 report" in mime
          assert "Content-Type: application/json" in mime
          assert json.dumps(body) in mime
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gmail_client.py::test_send_stubbed_returns_id_and_raw` passes.

- [x] **E8** — `tests/test_reporting/test_gmail_client.py` — edit — add
      `test_send_raises_when_no_token` (proves the gate / fail-soft branch): with
      `build_credentials` returning `None`, `send` raises `FileNotFoundError` (which
      `maybe_send_report` will catch):
      ```python
      def test_send_raises_when_no_token():
          with patch("src.reporting.gmail_client.build_credentials", return_value=None):
              sender = GmailSender("secrets/c.json", "secrets/t.json")
              try:
                  sender.send("a@b.com", "s", {})
                  assert False, "expected FileNotFoundError"
              except FileNotFoundError:
                  pass
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gmail_client.py::test_send_raises_when_no_token` passes.

- [x] **E9** — `tests/test_reporting/test_gating.py` — create — add imports and a helper
      that builds a minimal `Config`-like object with a `report` dict:
      ```python
      """Gating, fail-soft, env-override, and hygiene tests for maybe_send_report."""
      import os
      from unittest.mock import patch, MagicMock

      from src.game.engine import SeriesResult, SubGameResult


      class _Cfg:
          def __init__(self, report):
              self.report = report


      def _res():
          return SeriesResult(
              sub_games=[SubGameResult("COP", 20, 5, 7, "A", "B")],
              group_a_total=20, group_b_total=5,
          )
      ```
      **Check:** `uv run python -m py_compile tests/test_reporting/test_gating.py` succeeds after E10+.

- [x] **E10** — `tests/test_reporting/test_gating.py` — edit — add
      `test_noop_when_disabled` (AC5): with `enabled=False`, the gmail service is never
      built:
      ```python
      def test_noop_when_disabled():
          cfg = _Cfg({"enabled": False, "to": "x@y.com", "subject": "s",
                      "credentials_path": "c.json", "token_path": "t.json"})
          with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
               patch("googleapiclient.discovery.build") as mock_build:
              from src.reporting.gmail_client import maybe_send_report
              maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
          MockSender.assert_not_called()
          mock_build.assert_not_called()
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_noop_when_disabled` passes.

- [x] **E11** — `tests/test_reporting/test_gating.py` — edit — add
      `test_noop_when_no_token` (AC5): `enabled=True` but token file absent → no-op:
      ```python
      def test_noop_when_no_token(tmp_path, monkeypatch):
          token = tmp_path / "nope.json"   # does not exist
          cfg = _Cfg({"enabled": True, "to": "x@y.com", "subject": "s",
                      "credentials_path": "c.json", "token_path": str(token)})
          monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
          with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
               patch("googleapiclient.discovery.build") as mock_build:
              from src.reporting.gmail_client import maybe_send_report
              maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
          MockSender.assert_not_called()
          mock_build.assert_not_called()
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_noop_when_no_token` passes.

- [x] **E12** — `tests/test_reporting/test_gating.py` — edit — add
      `test_send_called_when_enabled_and_token_present` (AC5 positive branch): create a
      real token file, `enabled=True`, and assert `GmailSender.send` is called once. **Patch
      `build_report`** too — the `_Cfg` stub only carries `.report`, but the real
      `build_report` reads `config.agents`/`.scoring`/`.grid_size`/etc.; patching it isolates
      the gate/send mechanics (the builder shape is already covered by `test_report.py`):
      ```python
      def test_send_called_when_enabled_and_token_present(tmp_path, monkeypatch):
          token = tmp_path / "token.json"
          token.write_text("{}")
          cfg = _Cfg({"enabled": True, "to": "x@y.com", "subject": "s",
                      "credentials_path": "c.json", "token_path": str(token)})
          monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
          with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
               patch("src.reporting.gmail_client.build_report",
                     return_value={"schema_version": 1}) as mock_build:
              MockSender.return_value.send.return_value = "mid-1"
              from src.reporting.gmail_client import maybe_send_report
              maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
          MockSender.assert_called_once()
          MockSender.return_value.send.assert_called_once()
          mock_build.assert_called_once()
          args = MockSender.return_value.send.call_args.args
          assert args[0] == "x@y.com"
          assert args[1] == "s"
          assert isinstance(args[2], dict) and args[2]["schema_version"] == 1
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_send_called_when_enabled_and_token_present` passes.

- [x] **E13** — `tests/test_reporting/test_gating.py` — edit — add
      `test_fail_soft_swallows_send_error` (AC6): inject a `send` that raises; the hook
      must not propagate. **Patch `build_report`** (same reason as E12 — `_Cfg` lacks the
      attrs the real builder reads; without the patch the swallowed error would be an
      `AttributeError` from `build_report`, not the `RuntimeError` from `send` this test
      intends):
      ```python
      def test_fail_soft_swallows_send_error(tmp_path, monkeypatch):
          token = tmp_path / "token.json"
          token.write_text("{}")
          cfg = _Cfg({"enabled": True, "to": "x@y.com", "subject": "s",
                      "credentials_path": "c.json", "token_path": str(token)})
          monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
          with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
               patch("src.reporting.gmail_client.build_report",
                     return_value={"schema_version": 1}):
              MockSender.return_value.send.side_effect = RuntimeError("gmail exploded")
              from src.reporting.gmail_client import maybe_send_report
              maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")   # must not raise
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_fail_soft_swallows_send_error` passes.

- [x] **E14** — `tests/test_reporting/test_gating.py` — edit — add
      `test_env_overrides_flip_gate_and_path` (AC8): uses the real `load_config` so the
      env-override wiring in `config.py` is exercised:
      ```python
      def test_env_overrides_flip_gate_and_path(monkeypatch, tmp_path):
          monkeypatch.setenv("REPORT_ENABLED", "true")
          token = tmp_path / "override.json"
          token.write_text("{}")
          monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token))
          from src.game.config import load_config
          cfg = load_config("config.yaml")
          assert cfg.report["enabled"] is True
          assert cfg.report["token_path"] == str(token)
          # and the hook now reaches the sender (token exists at the overridden path)
          with patch("src.reporting.gmail_client.GmailSender") as MockSender:
              MockSender.return_value.send.return_value = "mid-env"
              from src.reporting.gmail_client import maybe_send_report
              maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
          MockSender.return_value.send.assert_called_once()
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_env_overrides_flip_gate_and_path` passes.

- [x] **E15** — `tests/test_reporting/test_gating.py` — edit — add `test_gitignore_and_env_example`
      (AC10): static hygiene guards:
      ```python
      def test_gitignore_and_env_example():
          from pathlib import Path
          gi = Path(".gitignore").read_text(encoding="utf-8")
          assert "secrets/" in gi
          assert "gmail_credentials.json" in gi
          assert "gmail_token.json" in gi
          env = Path(".env.example").read_text(encoding="utf-8")
          for var in ["REPORT_ENABLED", "REPORT_TO", "GMAIL_CREDENTIALS_PATH", "GMAIL_TOKEN_PATH"]:
              assert var in env, f"{var} missing from .env.example"
          # config.yaml has no real secret
          cfg = Path("config.yaml").read_text(encoding="utf-8")
          assert "gmail_token.json" in cfg   # the default path is fine
          assert "token.json" not in cfg.replace("gmail_token.json", "")  # no stray token content
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_gitignore_and_env_example` passes.

- [x] **E16** — `tests/test_reporting/test_gating.py` — edit — add
      `test_reporting_files_at_most_150_lines` (AC11 line-count guard):
      ```python
      def test_reporting_files_at_most_150_lines():
          from pathlib import Path
          for p in [
              "src/reporting/__init__.py",
              "src/reporting/report.py",
              "src/reporting/gmail_client.py",
              "src/reporting/auth.py",
              "src/reporting/__main__.py",
          ]:
              lines = len(Path(p).read_text(encoding="utf-8").splitlines())
              assert lines <= 150, f"{p} has {lines} lines (max 150)"
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_reporting_files_at_most_150_lines` passes.

- [x] **E17** — `tests/test_reporting/test_gating.py` — edit — add
      `test_no_hardcoded_lecturer_address` (AC11 no-hardcode guard): the lecturer address
      appears only in `config.yaml`, never in `src/`:
      ```python
      def test_no_hardcoded_lecturer_address():
          from pathlib import Path
          addr = "rmisegal+uoh26b@gmail.com"
          for p in Path("src").rglob("*.py"):
              t = p.read_text(encoding="utf-8")
              assert addr not in t, f"{p} hard-codes the lecturer address"
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_no_hardcoded_lecturer_address` passes.

- [x] **E18** — `tests/test_reporting/test_gating.py` — edit — add
      `test_build_credentials_returns_none_when_no_token` (covers `auth.py`'s load-bearing
      no-op branch — without this the F2 coverage gate fails on `auth.py`, since every other
      test patches `build_credentials` out):
      ```python
      def test_build_credentials_returns_none_when_no_token(tmp_path):
          from src.reporting.auth import build_credentials
          # token path does not exist -> the gate's no-op branch
          assert build_credentials("c.json", str(tmp_path / "nope.json")) is None
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_build_credentials_returns_none_when_no_token` passes.

- [x] **E19** — `tests/test_reporting/test_gating.py` — edit — add
      `test_build_credentials_refreshes_expired_token` (covers the refresh + re-persist +
      `return creds` branch of `auth.py`):
      ```python
      def test_build_credentials_refreshes_expired_token(tmp_path):
          from unittest.mock import patch, MagicMock
          token = tmp_path / "token.json"
          token.write_text('{"dummy": "token"}')
          fake_creds = MagicMock()
          fake_creds.expired = True
          fake_creds.refresh_token = "refresh-x"
          fake_creds.to_json.return_value = '{"dummy": "token"}'
          with patch("google.oauth2.credentials.Credentials.from_authorized_user_info",
                     return_value=fake_creds), \
               patch("google.auth.transport.requests.Request"):
              from src.reporting.auth import build_credentials
              result = build_credentials("c.json", str(token))
          assert result is fake_creds
          fake_creds.refresh.assert_called_once()
          assert token.read_text() == '{"dummy": "token"}'   # re-persisted via to_json()
      ```
      **Check:** `uv run pytest -q tests/test_reporting/test_gating.py::test_build_credentials_refreshes_expired_token` passes.

---

## Phase F — Gate verification and full suite

- [x] **F1** — run the targeted reporting tests:
      ```powershell
      uv run pytest -q tests/test_reporting/
      ```
      **Check:** all tests in `tests/test_reporting/` pass, none skipped, none erroring.

- [x] **F2** — run the coverage gate on the new package:
      ```powershell
      uv run pytest -q tests/test_reporting/ --cov=src.reporting --cov-report=term-missing --cov-fail-under=85
      ```
      **Check:** coverage report shows `src.reporting` at ≥ 85% and the command exits 0.
      The only uncovered lines should be `cmd_auth` / `__main__` (marked `# pragma: no cover`).
      `auth.build_credentials` is covered by E18 (no-token branch) + E19 (refresh branch);
      `report.build_report` by E3–E5; `gmail_client.GmailSender.send` by E7–E8;
      `maybe_send_report` by E10–E14.

- [x] **F3** — run ruff on all changed modules:
      ```powershell
      uv run ruff check src/reporting/ src/game/config.py src/orchestrator/__main__.py tests/test_reporting/
      ```
      **Check:** ruff reports zero issues. Fix any issues before proceeding.

- [x] **F4** — run full regression suite:
      ```powershell
      uv run pytest -q
      ```
      **Check:** output reports **≥ 165 tests passed**, 0 failed, 0 errors. No real send
      occurred (no `Report sent:` line in output). If any previously-passing test now
      fails, diagnose and fix the regression before proceeding.

- [x] **F5** — verify deps + lock:
      ```powershell
      uv run python -c "
      import tomllib
      d = tomllib.loads(open('pyproject.toml').read())
      dev = d['dependency-groups']['dev']
      for pkg in ['google-auth', 'google-auth-oauthlib', 'google-api-python-client']:
          assert any(p.startswith(pkg) for p in dev), f'{pkg} missing from dev group'
      print('ok')
      "
      ```
      **Check:** the command prints `ok` (AC12). Confirm `uv.lock` was updated by `uv lock`.

---

## Phase G — MANUAL operator acceptance (not automated)

**These are human-operator steps, not code boxes. They require a Google account, a Google
Cloud Console OAuth client (credential.json), and a browser. The code and tests are
complete before this phase. Run these only after F4 is green.**

> **G1 — Download OAuth credentials (MANUAL):**
> In Google Cloud Console → APIs & Services → Credentials → Create OAuth client ID
> (type: Desktop app). Download the JSON as `secrets/gmail_credentials.json`. Enable the
> Gmail API on the project. Never commit `secrets/` (it is git-ignored).

> **G2 — One-time OAuth login (MANUAL):**
> `python -m src.reporting auth` — opens a browser, consents with the account that will
> send mail (sender = this account). Writes `secrets/gmail_token.json` (refresh token).

> **G3 — Enable + run a real series (MANUAL):**
> Either set `report.enabled: true` in `config.yaml` OR `export REPORT_ENABLED=true`,
> then `python -m src.orchestrator`. After the series, the hook sends the JSON body to
> `rmisegal+uoh26b@gmail.com` and logs `Report sent: message id <id>`.

> **G4 — Update README.md (MANUAL):**
> Add an `## Email reporting` section with: the one-time OAuth login steps
> (`python -m src.reporting auth`), the `report:` config block, and the sent message id
> proof from G3.

> **G5 — Update ROADMAP.md (MANUAL — last step):**
> Set step 8 status to ✅ in the table and append a progress-log line (date, what was done).

---

## Acceptance-coverage matrix

| PRD acceptance criterion | Satisfying TODO boxes | Tests / checks |
|--------------------------|-----------------------|----------------|
| AC1 Report shape | B2–B4 | `test_report.py::test_build_report_full_shape` (E3) |
| AC2 Resizable | B3 | `test_report.py::test_build_report_resizable_3x3` (E4) |
| AC3 No secrets in body | B3, B4 | `test_report.py::test_report_has_no_secrets` (E5) |
| AC4 GmailSender stubbed send | C5–C6 | `test_gmail_client.py::test_send_stubbed_returns_id_and_raw` (E7) |
| AC5 Gating no-op | C7, D2 | `test_gating.py::test_noop_when_disabled`/`test_noop_when_no_token` (E10–E11) |
| AC6 Fail-soft | C7 | `test_gating.py::test_fail_soft_swallows_send_error` (E13) |
| AC7 Orchestrator hook + suite | D1–D2 | full `uv run pytest -q` ≥ 165 pass (F4) |
| AC8 Config + env overrides | A3–A6 | `test_gating.py::test_env_overrides_flip_gate_and_path` (E14) |
| AC9 Live send (MANUAL) | D3 + G1–G4 | README "Email reporting" + sent message id |
| AC10 Hygiene artifacts | A7–A8 | `test_gating.py::test_gitignore_and_env_example` (E15) |
| AC11 Segal gate | B4, C4, C8, F2–F3 | ruff + coverage ≥85% + ≤150-line guard (E16) + no-hardcode (E17) + `build_credentials` coverage (E18–E19) |
| AC12 Deps | A1 | `pyproject.toml` + `uv.lock` inspection (F5) |

---

## Definition of Done

- [ ] All boxes A1–F5 are ticked and their Checks passed.
- [ ] Phase G manual steps are completed by the operator (OAuth login + live send + README).
- [ ] All PRD acceptance criteria AC1–AC12 hold (`PRD_step8_gmail_api.md` §7).
      AC9 is the manual operator step.
- [ ] No lecturer address, token value, or real secret appears in any committed `src/` file.
- [ ] Every `src/reporting/` file is ≤ 150 lines.
- [ ] `uv run ruff check src/reporting/ src/game/config.py src/orchestrator/__main__.py tests/test_reporting/` passes.
- [ ] `uv run pytest -q tests/test_reporting/ --cov=src.reporting --cov-fail-under=85` passes.
- [ ] `uv run pytest -q` passes with ≥ 165 tests and no real send.
- [ ] `docs/_system/ROADMAP.md` updated: step 8 → ✅, progress-log line appended.
