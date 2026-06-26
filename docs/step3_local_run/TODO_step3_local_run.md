# TODO — Step 3: Full local run

> Implements `PRD_step3_local_run.md` + `PLAN_step3_local_run.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**
> One step = one commit = one `/relay-next`. When ready to build, copy these into `docs/PROGRESS.md`.

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never hard-code** game parameters, ports, or hosts — read them from `config.yaml` / `Config`. No literal `5` / `8001` / `8002` in `src/orchestrator/`.
4. Do not assume a 5×5 grid; bounds always come from `config.grid_size`.
5. If a box seems ambiguous, STOP and ask — do not guess.
6. **Reuse the Step-1 engine** (`apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`, `SubGameResult`/`SeriesResult`, role-swap). The only new behavior is "validate over the wire before applying" and "route a message." Do not re-implement a rule.
7. **Servers stay stateless** — do NOT add `get_state`/`apply_move`/`inbox`/`reset` tools. The referee owns the only `GameState`.
8. **Write `referee.py` against the `ServerGateway` protocol, never a concrete client.** Tests must run **without opening real sockets** (use `InMemoryGateway`).
9. Run every command from the repository root (the folder containing `config.yaml`).

## Conventions
- Language/runtime: **Python 3.12**. Source root: `src/` · Tests: `tests/`.
- Each box format: **ID · file · action · detail · Check.**
- **Library:** the standalone **`fastmcp`** package (3.x). `from fastmcp import Client`. The in-memory client wraps a server object: `Client(build_cop_server(config))`; the HTTP client wraps a URL: `Client("http://host:port/…")`. Both read tool returns as `result.data`.
- **Every tool return is a `dict`** `{ "ok": bool, "reason": str, ... }`, read back as `result.data`.
- **Message envelope** is `{ "from": str, "turn": int, "ts": str, "text": str }`. `text` is free natural language. **NO** coordinate fields — never add `row`/`col`/`x`/`y`/`pos`.
- **Move names** are `Move` enum members (`src/game/moves.py`): `N S E W NE NW SE SW PLACE_BARRIER`. `GreedyMover` never proposes `PLACE_BARRIER`.
- **One per-ply record shape** (PLAN §3) is shared by the in-memory transcript and each JSONL line — build it once, append + write the same dict.

---

## Phase A — config & mover groundwork

- [x] **A1** — `src/game/config.py` — edit — add an optional trailing field `output_run_dir: str = "runs"` to `Config`, and in `load_config` set it from `data["output"]["run_dir"]` **if an `output:` block is present**, else keep the default `"runs"`. Field must be **last** so existing positional `Config(...)` construction stays valid.
      **Check:** `python -c "from src.game.config import load_config; print(load_config('config.yaml').output_run_dir)"` prints `runs` (block present) and the existing `tests/test_game/test_config.py` still passes.

- [x] **A2** — `config.yaml` — edit — append an optional `output:` block (keep all existing keys unchanged):
      ```yaml
      output:
        run_dir: "runs"
      ```
      **Check:** `python -c "import yaml; print(yaml.safe_load(open('config.yaml'))['output']['run_dir'])"` prints `runs`.

- [x] **A3** — `.gitignore` — edit — add a line `runs/` so replay logs are not committed.
      **Check:** `git check-ignore runs/anything.jsonl` prints `runs/anything.jsonl`.

- [x] **A4** — `src/game/movers.py` — edit — add `class GreedyMover` with `choose_move(self, state) -> Move` (satisfies FR-O6): from `legal_moves(state)` drop `Move.PLACE_BARRIER`; if `state.to_move == "COP"` choose the candidate **minimizing** Chebyshev distance `max(|dr|, |dc|)` from the resulting cop position to `state.thief_pos`; if `"THIEF"` **maximize** Chebyshev distance from the resulting thief position to `state.cop_pos`. Break ties by `Move` declaration order (iterate candidates in enum order; keep the first best — deterministic, no RNG).
      **Check:** a quick REPL: a Cop at `(0,0)` with Thief at `(2,2)` on 3×3 returns `Move.SE`; a Thief at `(2,2)` with Cop at `(2,1)` returns a move increasing distance. `pytest -q` still green.

## Phase B — the gateway seam

- [x] **B1** — `src/orchestrator/__init__.py` — new — empty file to make `src.orchestrator` an importable package.
      **Check:** `python -c "import src.orchestrator; print('ok')"` prints `ok`.

- [x] **B2** — `src/orchestrator/recorders.py` — new — add the `Telemetry` class first (referenced by the gateway): records `(tool_name, ms)` samples via `record(tool_name, ms)`, stores boot pings via `set_boot_ping(cop_ms, thief_ms)`, and exposes `summary() -> dict` = `{calls, avg_ms, p95_ms, boot_ping:{cop_ms, thief_ms}}`. Keep it ≤150 lines (this file gains more recorders in Phase D).
      **Check:** `Telemetry` with two `record(...)` calls reports `calls == 2` and a numeric `avg_ms`.

- [x] **B3** — `src/orchestrator/gateway.py` — new — define the `ServerGateway` `Protocol` (async `ping`, `validate_location`, `validate_move`, `place_barrier`, `send_message` per PLAN §2) and **`InMemoryGateway`** (`__init__(self, server, name, telemetry)`; opens `Client(server)`; each method `await self._client.call_tool(name, args)`, times it, calls `telemetry.record(...)`, returns `result.data`). Satisfies FR-O2 (test impl) + FR-O10 (timing in gateway).
      **Check:** `test_gateway_inmemory` — `async with` an `InMemoryGateway(build_cop_server(config))`, call `ping()`, assert `result["ok"]` and that telemetry recorded exactly one sample.

- [x] **B4** — `src/orchestrator/gateway.py` — edit — add **`HttpGateway`** (`__init__(self, url, name, telemetry)`; wraps `Client(url)`; same method bodies as `InMemoryGateway`, returning `.data`). **VERIFY the live fastmcp HTTP client URL/path via context7 first** (PLAN §6) and record the confirmed URL form in a one-line comment. No host/port literals — caller passes the URL built from `config.servers`.
      **Check:** `python -c "from src.orchestrator.gateway import HttpGateway, InMemoryGateway, ServerGateway; print('ok')"` prints `ok` (no live server needed to import).

## Phase C — the referee loop

- [x] **C1** — `src/orchestrator/referee.py` — new — `async def run_sub_game(config, cop_gateway, thief_gateway, cop_mover, thief_mover, recorders) -> SubGameResult`: mirror `engine.play_sub_game` but per ply — pick the side-to-move's mover → `choose_move` → build flat args from ground-truth state → `await <side>_gateway.validate_move(...)` → on `ok` `apply_move` locally; on `not ok` raise (integration guard, FR-O3). Reuse `initial_state`, `is_capture`, `is_timeout`, `score_sub_game`, `SubGameResult`. (Message bus + recorders wired in C3/Phase D — leave a clear seam.)
      **Check:** `test_run_sub_game_3x3` via `InMemoryGateway` returns a `SubGameResult` whose `winner == "COP"` (greedy Cop captures on 3×3) — satisfies R-AC3.

- [x] **C2** — `src/orchestrator/referee.py` — edit — `async def run_series(config, cop_gateway, thief_gateway, group_a, group_b, recorders) -> SeriesResult`: copy the §4.4 role-swap from `engine.play_series`, awaiting `run_sub_game` each iteration; attribute each role's points to the right group; return `SeriesResult`. Satisfies FR-O4.
      **Check:** `test_run_series_band` — a full in-memory series returns group totals within `[30, 90]` (R-AC1 parity, port-free).

- [x] **C3** — `src/orchestrator/referee.py` — edit — wire the **message bus** (FR-O5): each ply, the moving agent emits a free-text envelope `{from, turn, ts, text}`, the referee `await <side>_gateway.send_message(envelope)`, then delivers it to the other side (record as `last_msg`) and into the per-ply record. Envelope carries **no coordinate fields**.
      **Check:** `test_message_bus_delivers` asserts each emitted envelope reaches the other agent and is recorded; `test_envelope_has_no_coords` asserts the envelope keys are exactly `{from, turn, ts, text}` — satisfies R-AC4.

## Phase D — instrumentation seams (recorders)

- [x] **D1** — `src/orchestrator/recorders.py` — edit — add `observe(state, side) -> dict` (FR-O11) returning `{self, sees_opponent, opponent_pos, last_msg, barriers}`; Step-3 policy = full visibility (record ground truth), but the `sees_opponent`/`opponent_pos` fields **must** be present. Wire `referee.py` to record both `obs["COP"]` and `obs["THIEF"]` per ply.
      **Check:** `test_observe_schema` asserts `view["self"]` matches ground truth and all five keys exist for both sides — satisfies R-AC9.

- [x] **D2** — `src/orchestrator/recorders.py` — edit — add `render_board(state) -> str` (FR-O12): a grid string sized to `config.grid_size` (via `state.board.rows/cols`) with `C`, `T`, `#` for barriers, `.` elsewhere.
      **Check:** `test_render_board_3x3` — a known 3×3 state renders the expected string — satisfies R-AC10.

- [x] **D3** — `src/orchestrator/recorders.py` — edit — add `class ReplayLog` (FR-O9): `__init__(self, run_dir)` creates the dir if missing and opens `<run_dir>/<timestamp>.jsonl`; `write(record)` appends `json.dumps(record) + "\n"`. Wire `referee.py` to build the ONE per-ply record (PLAN §3), append it to the in-memory transcript, AND `replay_log.write(...)` the same dict.
      **Check:** `test_replay_log_roundtrip` — a 3×3 series writes a file whose line count == plies and every line round-trips through `json.loads` — satisfies R-AC7.

- [x] **D4** — `tests/test_orchestrator/test_telemetry.py` — new — assert the gateway records exactly one timing sample per tool call and `Telemetry.summary()` reports `calls`, `avg_ms`, `p95_ms`, `boot_ping`. Satisfies FR-O10 / R-AC8.
      **Check:** `pytest -q tests/test_orchestrator/test_telemetry.py` green.

## Phase E — entry point & resizability

- [x] **E1** — `src/orchestrator/__main__.py` — new — load config; build two `HttpGateway`s from `config.servers.{cop,thief}.{host,port}`; `ping` both at boot (record boot latency; on `ConnectionError`/refused print the two exact start commands `python -m src.mcp_servers.cop_server` / `...thief_server` and `sys.exit(1)` — FR-O7); `asyncio.run(run_series(...))` with `GreedyMover`s for both groups; stream `render_board` + transcript line per ply; write the JSONL replay; print `SeriesResult` + `telemetry.summary()`.
      **Check (manual demo, R-AC1):** start both servers in two terminals, then `python -m src.orchestrator` connects over HTTP, prints the transcript + a `SeriesResult` with totals in `[30, 90]`. With servers **down**, it prints "start the servers first" and exits non-zero (R-AC6).

- [x] **E2** — `tests/test_orchestrator/test_resizable.py` — new — build the servers on a 3×3 override and run a port-free series via `InMemoryGateway`; assert it completes and reports engine-parity scores. Also assert `test_every_move_validated` (a `validate_move` precedes each applied ply, FR-O3 / R-AC2).
      **Check:** `pytest -q` green (existing 39 + all new orchestrator tests); no real sockets opened — satisfies R-AC5.

- [x] **E3** — repo root — verify — grep for hard-coded literals and confirm the gate: no `5` / `8001` / `8002` / `127.0.0.1` in `src/orchestrator/`.
      **Check:** `grep -rnE "8001|8002|127\.0\.0\.1|\b5\b" src/orchestrator/` returns nothing — satisfies R-AC6.

---

## Coverage matrix (§6 — every requirement has a test)
| Requirement | Step(s) | Test |
|-------------|---------|------|
| FR-O1 (orchestrator package) | B1, E1 | manual run + import check |
| FR-O2 (`ServerGateway` seam) | B3, B4 | `tests/test_orchestrator/test_gateway.py::test_gateway_inmemory` |
| FR-O3 (validate-before-apply) | C1, E2 | `test_orchestrator/test_resizable.py::test_every_move_validated` (R-AC2) |
| FR-O4 (referee owns state) | C1, C2 | `test_orchestrator/test_referee.py::test_run_series_band` (R-AC1) |
| FR-O5 (message bus) | C3 | `test_orchestrator/test_referee.py::test_message_bus_delivers` (R-AC4) |
| FR-O6 (`GreedyMover`) | A4, C1 | `test_orchestrator/test_referee.py::test_greedy_cop_captures_3x3` (R-AC3) |
| FR-O7 (friendly failure) | E1 | `test_orchestrator/test_main.py::test_friendly_failure` (R-AC6) |
| FR-O8 (config-driven/resizable) | A1–A2, E2, E3 | `test_orchestrator/test_resizable.py` + grep (R-AC5, R-AC6) |
| FR-O9 (replay log) | D3 | `test_orchestrator/test_recorders.py::test_replay_log_roundtrip` (R-AC7) |
| FR-O10 (telemetry) | B2, B3, D4 | `test_orchestrator/test_telemetry.py` (R-AC8) |
| FR-O11 (observation log) | D1 | `test_orchestrator/test_recorders.py::test_observe_schema` (R-AC9) |
| FR-O12 (ASCII render) | D2 | `test_orchestrator/test_recorders.py::test_render_board_3x3` (R-AC10) |

## `{TBD}` — LOCKED by Director 2026-06-25 (§2.5)
1. **fastmcp HTTP client URL/path** — ✅ **LOCKED: verify-then-build.** Do not pin a URL now; box **B4** confirms the exact form live via context7 and records it in a one-line comment before writing `HttpGateway`. Phase A–C never touch HTTP (in-memory only), so this does not block the start.
2. **`output:` config block** — ✅ **LOCKED: approved.** Add optional `output.run_dir`, default `"runs"` (operational, not a game value — defaulting allowed per PRD §4).
3. **Message text source** — ✅ **LOCKED: placeholder now.** Step 3 emits placeholder free-text per ply (e.g. `"<role> plays <move>"`); real NL deferred to Step 5. The envelope schema `{from, turn, ts, text}` is final.

> Once approved, `/relay-next` transcribes these TODOs into code one box at a time, and `/relay-verify <hash>` holds each box to the Segal §19.1 Table-5 gate (ruff, pytest, coverage ≥85%, ≤150 lines/file, no hard-coded values, no secrets, uv-only).
