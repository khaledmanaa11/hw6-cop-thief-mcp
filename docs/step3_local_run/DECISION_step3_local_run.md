# DECISION — Step 3: Full local run

- **Roadmap position:** step 3 of 8 (`step3_local_run`)
- **Date discussed:** 2026-06-25
- **Status:** decision-written
- **Assignment references:** §13 Table 4 (step 3 "full local run, localhost, separate ports"); §4.1–4.4 (game rules/series); the standing server/client-split and config-driven constraints (WORKFLOW §6).

## 1. What this step is (one paragraph)
Step 3 is the **wiring step**. Steps 1 and 2 built two halves that have never touched:
a pure in-process engine (`src/game/`) and two stateless validate-only FastMCP servers
(`src/mcp_servers/`). Step 3 introduces an **orchestrator / referee** process that
connects over **real HTTP** to both servers (Cop on its port, Thief on its port), owns
the single ground-truth game state, and drives a full **6-sub-game series end-to-end**
where every ply is validated by the relevant server before the referee applies it. After
this step the project has its first genuinely *distributed* run: two networked servers +
a referee playing a complete series, with a printed move/message transcript. The step is
also **instrumented** — a reproducible replay log, network telemetry, a Dec-POMDP
observation log, and an ASCII board render — so the wiring is *provable* and the
architecture is visible (the graded value).

## 2. What it adds to the project
- A new package `src/orchestrator/` (the referee/client tier — the thing the README calls the orchestrator).
- An **HTTP client wrapper** that calls each server's tools (`ping`, `validate_move`, `validate_location`, `place_barrier`, `send_message`) and reads `result.data`.
- A **referee loop** that mirrors `engine.play_sub_game` / `play_series` but routes every move through a server `validate_move` round-trip before applying it locally with the engine.
- A **message bus**: each agent emits a free-text envelope via `send_message` (server validates it), the orchestrator routes it to the other agent and records a transcript.
- A **`GreedyMover`** in `src/game/movers.py` (Chebyshev pursue/evade) so the local run is a *meaningful* demo, not random flailing.
- A runnable entry point: `python -m src.orchestrator` that connects to both already-running servers, plays the series, and prints the transcript + `SeriesResult`.
- A new test package `tests/test_orchestrator/` exercising the loop **port-free** via the in-memory `Client`.

**Creative instrumentation (4 baked-in extras — each a seam, not a finished feature):**
- **JSONL replay log** — the referee writes every ply (state, proposed move, server `{ok,reason}` verdict, message envelope, scores) to `runs/<timestamp>.jsonl`. Deterministic greedy ⇒ reproducible. **Reused by Step 6** (GUI replays it) and **Step 8** (Gmail report reads it). This is the architectural spine of the whole project.
- **Network telemetry** — `ping` both servers at boot and record per-call round-trip latency; print a telemetry summary. *Proves the run is really distributed over HTTP* (not secretly in-process) and foreshadows Step 7 cloud latency.
- **Dec-POMDP observation log** — per ply, record each agent's *partial view* (what it observes) alongside ground truth, even though `GreedyMover` ignores it. Gives the graded README's Dec-POMDP model real ⟨Ωᵢ, O⟩ data; it is the exact seam **Step 5** fills with NL inference.
- **ASCII board + readable transcript** — render the board each ply in the CLI with a human-readable move/message line. Satisfies the README's required *"visual/CLI proof of correct communication"* now; precursor to the Step 6 GUI.

## 3. Scope
**In scope:**
- Orchestrator package: HTTP client wrapper, referee loop, message bus, `__main__`.
- A single role-aware `GreedyMover` (pursue when Cop, evade when Thief) behind the existing `choose_move` seam.
- Every applied move is first validated by the side-to-move's server over the wire.
- A full series (default 6 sub-games, role-swapping per §4.4) runs end-to-end and reports group totals.
- Friendly failure when servers aren't running (clear "start the servers first" message, non-zero exit).
- Resizability proven at 3×3 in tests (no hard-coded 5×5).
- The 4 instrumentation extras above: **JSONL replay log**, **network telemetry** (boot ping + per-call latency), **Dec-POMDP per-agent observation log**, and **ASCII board + readable transcript** — built as *thin seams* (record/emit only; nothing consumes them yet beyond printing/writing).

**Out of scope (deferred):**
- The real strategy brain — tunable heuristics + Q-Table/learning → **Step 4**.
- Barrier *strategy* (when/where the Cop should wall) → **Step 4**. (Step 3 wires and tests the `place_barrier` validation path but `GreedyMover` does not place barriers.)
- Free natural-language understanding / location inference / deception → **Step 5** (Step 3 messages are free-text but agents don't act on them).
- Stateful server tools (`get_state`/`apply_move`/`inbox`/`reset`) — referee stays authoritative; servers stay stateless.
- Auto-launching servers as subprocesses (Director chose **manual start**); cloud deploy → Step 7.
- **Consuming** the instrumentation: the GUI that *replays* the JSONL → Step 6; the Gmail report that *reads* it → Step 8; acting on the observation log (NL location inference/deception) → Step 5. Step 3 only **produces** these records.

## 4. Chosen approach (and what we rejected)
**Decision:** A **referee-authoritative orchestrator** connects as an **HTTP client** to two
**manually-started** servers. Servers stay **validate-only**; the referee applies moves
locally with the engine. Agent messages flow through the **orchestrator as a message bus**.
Agents are driven by a **minimal `GreedyMover`** now; the full decision engine is Step 4.

**Why:** This honors the Step 2 lock-in (referee owns state, servers are stateless tool
faces, LLM/brain lives in the client) with the smallest possible step, while still
satisfying §13's "localhost, separate ports" by using real HTTP transport. It keeps the
networking demo and the strategy work on separate steps so they are debugged independently.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Orchestrator connects to manually-started HTTP servers | ✅ chosen | Real ports/transport; simplest orchestrator; matches Director's call |
| Orchestrator spawns servers as subprocesses | ❌ deferred | Nicer one-command demo but more orchestrator complexity; revisit at Step 7 |
| In-memory `Client` only (no ports) | ❌ rejected for the *run* | Fails §13 "separate ports"; proves no networking. (Kept for **tests** only.) |
| Servers validate-only, referee applies | ✅ chosen | Preserves stateless-server contract; no rule duplication |
| Promote stateful `apply_move`/`get_state` to servers | ❌ rejected | Duplicates referee authority; contradicts Step 2 design; pulls Step 4 work in |
| Orchestrator as message bus | ✅ chosen | Routes validated messages with no new server state |
| Per-server stateful inbox now | ❌ rejected | Server state contradicts the lock; NL content isn't due until Step 5 |
| `GreedyMover` now, full engine Step 4 | ✅ chosen | Meaningful demo without gutting Step 4 |
| Full heuristic + Q-Table now | ❌ rejected | Debugs strategy + networking together; collapses Step 4 |

## 5. Dependencies & interfaces
- **Consumes from prior steps:**
  - `src/game/`: `load_config`, `initial_state`, `apply_move`, `legal_moves`, `Move`, `GameState`, and rules `is_capture`/`is_timeout`/`score_sub_game`; result dataclasses `SubGameResult`/`SeriesResult` and the role-swapping series semantics (§4.4) from `engine.py`.
  - `src/mcp_servers/`: `build_cop_server(config)` / `build_thief_server(config)` and the live tool contract from Step 2 — flat-arg `validate_move(to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move)`, `validate_location(pos, barriers)`, `place_barrier(pos, cop_barriers_left, barriers)` (**Cop only**), `send_message(envelope)`, `ping()`; all return `{ok, reason, ...}` read as `result.data`.
- **Exposes to later steps:**
  - A `Mover`-compatible `GreedyMover` for Step 4 to subclass/replace.
  - A **`ServerGateway`** seam (async `validate_move/validate_location/place_barrier/send_message/ping`) with two implementations — HTTP (prod) and in-memory (tests) — that Steps 5–7 reuse to swap transport/brains without touching the loop.
  - The orchestrator loop/transcript that Step 6 (GUI) renders and Step 8 (Gmail) reports on.
- **Touches config keys:** reads `servers.cop.{host,port}`, `servers.thief.{host,port}`, plus all existing game keys. **No new *game* keys** (deterministic tie-break, see §7). One **optional, operational** key may be added: `output.run_dir` (default `"runs"`) for the JSONL replay log — kept optional with a default so existing positional `Config` ctors stay valid (same pattern Step 2 used for `servers`). Not a game parameter, so it doesn't touch the no-hard-coding rule for game values; defaulting is fine.

## 6. Binding constraints (from the assignment)
- **Server/client split:** the brain/decision logic lives in the orchestrator (client); servers only expose tools. `GreedyMover` and the referee live in the client tier.
- **Servers stateless:** referee owns the only ground-truth `GameState`; servers receive state as call args and return validations.
- **No hard-coding / resizable:** grid, ports, hosts, counts all come from `config.yaml`; prove with a 3×3 test. No literal `5`/`8001`/`8002` in `src/orchestrator/`.
- **Free natural language ready:** message envelope stays `{from, turn, ts, text}` with **free-text only, no coordinate fields** (Step 2 seam #2), so Step 5 can drop in real NL.
- **Dec-POMDP seam:** keep a per-agent "view" boundary in mind — `GreedyMover` reads full state for now, but the gateway/message split is where Step 5's partial observation slots in.

## 7. Key design decisions
- **Files/modules to create:**
  - `src/orchestrator/__init__.py`
  - `src/orchestrator/gateway.py` — `ServerGateway` protocol + `HttpGateway` (wraps `fastmcp.Client(url)`) and `InMemoryGateway` (wraps `Client(server_obj)`); async methods return the tool's `.data` dict.
  - `src/orchestrator/referee.py` — server-routed `run_sub_game(config, gateways, cop_mover, thief_mover)` and `run_series(config, gateways, group_a, group_b)`; reuses engine rules + `apply_move`; builds a `transcript` and feeds the recorders below.
  - `src/orchestrator/recorders.py` — the 4 instrumentation seams, each a small isolated unit: `ReplayLog` (append-only JSONL writer to `output.run_dir`), `Telemetry` (per-call latency + boot ping summary), `observe(state, side) -> dict` (Dec-POMDP partial view), `render_board(state) -> str` (ASCII). Kept out of `referee.py` so the loop stays readable and each seam is unit-testable.
  - `src/orchestrator/__main__.py` — load config, build two `HttpGateway`s from `config.servers`, `ping` both (telemetry + friendly error + non-zero exit if refused), run the series, stream the ASCII board/transcript, write the JSONL replay, print the `SeriesResult` + telemetry summary.
  - `src/game/movers.py` — add `GreedyMover`.
  - `tests/test_orchestrator/` — port-free tests via `InMemoryGateway`, incl. one test per instrumentation seam.
- **Core data structures:**
  - Reuse `GameState`, `Move`, `SubGameResult`, `SeriesResult`.
  - **Message envelope:** `{"from": str, "turn": int, "ts": <iso/epoch>, "text": str}` — free text only.
  - **Transcript / replay record (one JSONL line per ply):** `{turn, side, move, verdict:{ok,reason}, message:<envelope>, cop_score?, thief_score?, obs:{COP:<view>, THIEF:<view>}, ground_truth:{cop_pos, thief_pos, barriers, moves_used}}`. The in-memory transcript and the JSONL line share this shape.
  - **Observation view** (`observe`): per-agent dict, e.g. `{"self": pos, "sees_opponent": bool, "opponent_pos": pos|null, "last_msg": str|null, "barriers": [...]}` — the ⟨Ωᵢ, O⟩ projection of ground truth. Step-3 policy: full visibility (records truth); the `sees_opponent`/`opponent_pos` fields are where Step 5 imposes partial observability.
  - **Telemetry:** per-call `(tool_name, ms)` samples + a summary `{calls, avg_ms, p95_ms, boot_ping:{cop_ms, thief_ms}}`.
- **Key signatures (intent):**
  - `class GreedyMover: choose_move(self, state) -> Move` — role-aware: if `state.to_move == "COP"` pick the legal **non-barrier** move minimizing **Chebyshev** distance to `thief_pos`; if `"THIEF"` pick the legal move maximizing Chebyshev distance to `cop_pos`. **Deterministic tie-break** by a fixed `Move` priority order (no RNG, fully reproducible). Never proposes `PLACE_BARRIER` (Step 4 owns barrier strategy).
  - `ServerGateway` (async): `validate_move(...)`, `validate_location(...)`, `place_barrier(...)`, `send_message(envelope)`, `ping()` — each returns the `{ok, reason, ...}` dict.
  - Referee per ply: pick side-to-move's mover → `choose_move` → build flat args from ground-truth state → `gateway.validate_move(...)` → on `ok` `apply_move` locally; on `not ok` raise/log (a correct mover never produces this — it's an integration guard) → mover emits free-text message → `gateway.send_message(envelope)` → append to transcript and deliver to the other side.
- **Telemetry hook point:** time calls **inside the gateway** (wrap each `call_tool`), so both `HttpGateway` and `InMemoryGateway` feed the same `Telemetry` object and the referee needs no timing code. (In-memory latencies will be ~0 — that's fine; the point is the HTTP path proves real network cost.)
- **Async model:** the referee loop and gateways are `async`; `__main__` uses `asyncio.run`. The series role-swap logic (§4.4) is copied from `engine.play_series` but awaits server-routed sub-games.
- **Chebyshev rationale:** moves are 8-directional (king moves), so Chebyshev distance equals the minimum number of moves — the correct greedy metric.

## 8. Acceptance criteria (how we know the step is done)
1. With both servers started manually (`python -m src.mcp_servers.cop_server` and `...thief_server`), `python -m src.orchestrator` connects over HTTP, plays a full `num_games` series, and prints a transcript + final `SeriesResult` with group totals in the §4.4 `[30, 90]` band.
2. **Every applied move was first validated by the side-to-move's server** (provable via the transcript/log — no move bypasses the gateway).
3. On a small grid (e.g. 3×3) the `GreedyMover` Cop **captures** the Thief within `max_moves`, and the engine's `score_sub_game` is what the referee reports (parity with engine rules).
4. The message bus delivers every emitted envelope to the other agent and records it in the transcript; envelopes contain only `{from, turn, ts, text}` (no coordinate fields).
5. `pytest -q` passes (existing 39 + new orchestrator tests), tests run **without opening real ports** (in-memory gateway), and include a **3×3 resizability** case.
6. No hard-coded grid/port/host literals in `src/orchestrator/`; running `__main__` with servers down prints a clear "start the servers first" message and exits non-zero.
7. **Replay log:** a series writes `runs/<timestamp>.jsonl` with one valid-JSON line per ply; replaying the file reproduces the same move sequence (deterministic greedy). A test asserts line count == plies and that each line round-trips through `json.loads`.
8. **Telemetry:** boot prints both servers' ping latency; the end-of-run summary reports call count + avg/p95 latency. A test asserts the gateway records one timing sample per tool call.
9. **Observation log:** every ply records a per-agent view for both COP and THIEF; a test asserts the view's `self` matches ground truth and the schema is stable (the seam Step 5 will tighten to partial visibility).
10. **ASCII render:** `render_board(state)` returns a grid string showing C, T, and `#` barriers sized to `config.grid_size`; a test checks a known 3×3 state renders correctly.

## 9. Resolved questions / open items
- **Q:** Subprocess vs manual vs in-memory for the run? → **A:** **Manual start**; orchestrator connects over HTTP. (In-memory reserved for tests; subprocess revisited at Step 7.)
- **Q:** Do servers gain state this step? → **A:** **No** — validate-only; referee applies locally.
- **Q:** How do messages reach the other agent? → **A:** **Orchestrator as message bus** (server validates, orchestrator routes/logs).
- **Q:** Random or heuristic agents? → **A:** **Minimal `GreedyMover`** (Chebyshev pursue/evade) now; full tunable heuristic + Q-Table is **Step 4**.
- **Q:** New config keys? → **A:** No new *game* keys (deterministic tie-break avoids a seed). One optional operational key `output.run_dir` (default `"runs"`) for the replay log.
- **Q:** Creative additions for this step? → **A:** Director approved **all four**: JSONL replay log, network telemetry, Dec-POMDP observation log, ASCII board + transcript — each scoped as a *seam/proof* (produced now, consumed by Steps 5/6/8 later).
- **Still open (note for Builder):** the exact `fastmcp` v3 HTTP client URL/path (e.g. `http://host:port/mcp`) and `Client(url)` usage — **verify live via context7 before writing the TODO**, same as Step 2 verified the server side.

## 10. Notes for the Builder session
- **Put the most TODO detail in `gateway.py` and `referee.py`.** The gateway is the single seam that makes the loop testable; spell out both `HttpGateway` and `InMemoryGateway` with copy-paste code, and write `referee.py` against the **protocol**, never against a concrete client.
- **Verify the live `fastmcp` client-over-HTTP API via context7 first** (server side is already confirmed: `FastMCP`, `@mcp.tool`, `mcp.run(transport="http", host, port)`; client reads `result.data`). Confirm the URL path and that `async with Client("http://host:port/...") as c: await c.call_tool(name, {...})` returns `.data` the same way the in-memory client does — that parity is what lets prod and tests share one referee.
- **Reuse, don't re-implement, the engine.** Import `apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`, and the `SubGameResult`/`SeriesResult` dataclasses + role-swap logic from `engine.py`. The only new behavior is "validate over the wire before applying" and "route a message."
- **`GreedyMover` is one class for both roles** — branch on `state.to_move`. Exclude `Move.PLACE_BARRIER` from its candidates. Use a fixed `Move` ordering for deterministic tie-breaks so tests and the demo are reproducible.
- **Async tests:** `pytest-asyncio` + `asyncio_mode="auto"` are already configured (Step 2). New tests use `InMemoryGateway(build_cop_server(config))` / `build_thief_server(config)` — **no real sockets**.
- **Friendly failure matters for grading the demo:** `__main__` should `ping` both servers up front and, on `ConnectionError`/refused, print the two exact server-start commands and exit non-zero rather than dumping a traceback.
- **Keep the 4 extras in `recorders.py`, not in the loop.** Each is small and independently testable; `referee.py` should just call them. The replay record and the in-memory transcript share ONE shape (§7) — build the dict once per ply, append to transcript, and write the same dict as a JSONL line. Don't diverge the two.
- **Telemetry lives in the gateway** (wrap `call_tool`), so it works identically for HTTP and in-memory and needs zero referee changes.
- **`observe()` records ground truth in Step 3** (full visibility) but MUST expose the `sees_opponent`/`opponent_pos` fields now — that stable schema is the contract Step 5 depends on. Don't omit them just because they're always true today.
- **`output.run_dir`** is optional with default `"runs"`; add it to `Config` as a trailing optional field (mirror how `servers` was added) and create the dir if missing. Add `runs/` to `.gitignore`.
