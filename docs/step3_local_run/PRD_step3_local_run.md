# PRD — Step 3: Full local run

| Field | Value |
|-------|-------|
| Component | `step3_local_run` (orchestrator / referee tier) | Version | 1.00 | Depends on | Step 1 (`src/game/`), Step 2 (`src/mcp_servers/`) |

- **Status:** triplet-built — awaiting Director approval (§2.5) before any code
- **Source:** `DECISION_step3_local_run.md`
- **Cross-links:** `PLAN_step3_local_run.md` (architecture) · `TODO_step3_local_run.md` (atomic build order)
- **Assignment references:** §13 Table 4 (step 3 "full local run, localhost, separate ports"); §4.1–4.4 (game rules / 6-sub-game series); §5 (server/client split); §6 (free natural-language messaging); standing config-driven / resizable constraints (WORKFLOW §6).

## 1. Description & theoretical background (§2.3)
Steps 1 and 2 built two halves that have never touched: a pure in-process engine (`src/game/`)
and two **stateless, validate-only** FastMCP servers (`src/mcp_servers/`). Step 3 is the **wiring
step**. It introduces an **orchestrator / referee** process that connects over **real HTTP** to both
servers (Cop on its port, Thief on its port), owns the single ground-truth `GameState`, and drives a
full **6-sub-game series end-to-end** where **every ply is validated by the side-to-move's server
before the referee applies it locally** with the Step-1 engine. Agent messages flow through the
orchestrator acting as a **message bus** (each free-text envelope is validated by a server, then
routed to the other agent and recorded). Agents are driven by a minimal, deterministic
**`GreedyMover`** (Chebyshev pursue/evade) so the demo is meaningful without pulling Step-4 strategy
forward. Theoretically this is the project's first genuinely **distributed Dec-POMDP run**: two
networked tool-servers plus a referee that is the only authority over state, instrumented so the
wiring is *provable* and the architecture is *visible* (the graded value).

## 2. Inputs / Outputs / performance metrics (§2.3)
- **Input:** `config.yaml` (all Step-1 game keys + `servers.{cop,thief}.{host,port}` from Step 2 + one optional `output.run_dir`, default `"runs"`); two already-running FastMCP servers reachable at the config host/ports.
- **Output:** a printed per-ply **ASCII board + readable move/message transcript**, a final `SeriesResult` (group A/B totals in the §4.4 `[30, 90]` band), a **JSONL replay log** at `runs/<timestamp>.jsonl` (one valid-JSON line per ply), a **telemetry summary** (boot ping + per-call latency), and a **Dec-POMDP observation log** (per-agent partial view per ply). Edge behavior: if a server is unreachable, print the two exact server-start commands and exit non-zero.
- **Performance:** correctness over speed — a default 6-sub-game series on 5×5 completes in well under a minute locally. Telemetry exists to *prove* real network cost (HTTP round-trips are non-zero; in-memory ≈ 0). No hard latency target; the metric is that the run is demonstrably over the wire.

## 3. Functional requirements
- **FR-O1 — Orchestrator package.** A new `src/orchestrator/` package is launchable as `python -m src.orchestrator`; it connects to both running servers, plays the series, and prints the transcript + `SeriesResult`.
- **FR-O2 — `ServerGateway` seam.** An async gateway protocol with methods `validate_move`, `validate_location`, `place_barrier`, `send_message`, `ping`, each returning the tool's `{ok, reason, …}` dict (read from `result.data`). Two implementations: `HttpGateway` (wraps `fastmcp.Client(url)`, used by the run) and `InMemoryGateway` (wraps `Client(server_obj)`, used by tests). The referee is written **against the protocol**, never a concrete client.
- **FR-O3 — Validate-before-apply.** Every applied move is first round-tripped through the **side-to-move's** `gateway.validate_move(...)`; only on `ok:true` does the referee `apply_move` locally. A correct mover never produces an illegal move — a `not ok` is an integration guard (raise/log).
- **FR-O4 — Referee owns state; servers stay stateless.** The referee holds the only ground-truth `GameState`; it reuses the Step-1 engine (`apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`, `SubGameResult`/`SeriesResult`) and the §4.4 role-swap. No new server state, no rule duplication.
- **FR-O5 — Message bus.** Each agent emits a free-text envelope `{from, turn, ts, text}`; the orchestrator validates it via `send_message`, delivers it to the other agent, and appends it to the transcript. The envelope has **no coordinate fields** (Step-2 seam #2 preserved for Step 5).
- **FR-O6 — `GreedyMover`.** One role-aware class in `src/game/movers.py`: if `to_move == "COP"`, pick the legal **non-barrier** move minimizing **Chebyshev** distance to `thief_pos`; if `"THIEF"`, maximize Chebyshev distance to `cop_pos`. **Deterministic tie-break** by fixed `Move` declaration order (no RNG). Never proposes `PLACE_BARRIER` (Step 4 owns barrier strategy).
- **FR-O7 — Friendly failure.** With servers down, `__main__` pings up front and, on connection refused, prints the two exact start commands and exits non-zero (no traceback dump).
- **FR-O8 — Config-driven / resizable.** Grid, ports, hosts, counts all come from `config.yaml`; no literal `5` / `8001` / `8002` in `src/orchestrator/`. A 3×3 test proves resizability.
- **FR-O9 — Replay log (instrumentation seam).** A series writes `runs/<timestamp>.jsonl`, one valid-JSON line per ply, sharing ONE record shape with the in-memory transcript. Deterministic greedy ⇒ reproducible. *(Produced now; consumed by Step 6 GUI / Step 8 Gmail.)*
- **FR-O10 — Telemetry (instrumentation seam).** Timing is captured **inside the gateway** (wrap each `call_tool`), so HTTP and in-memory feed the same `Telemetry`; boot prints both servers' ping latency and the end-of-run summary reports call count + avg/p95.
- **FR-O11 — Observation log (instrumentation seam).** Per ply, record each agent's partial view for both COP and THIEF (the ⟨Ωᵢ, O⟩ projection). Step-3 policy is full visibility, but the `sees_opponent` / `opponent_pos` fields **must** exist now — that stable schema is the contract Step 5 tightens.
- **FR-O12 — ASCII render (instrumentation seam).** `render_board(state)` returns a grid string sized to `config.grid_size` showing `C`, `T`, and `#` barriers; printed each ply with a human-readable move/message line.

## 4. Constraints, limitations, alternatives considered (§2.3)
- **Server/client split (§5):** the brain (`GreedyMover`) and referee live in the client tier; servers expose tools only. · Alternative rejected: promote stateful `apply_move`/`get_state` to servers — duplicates referee authority, contradicts Step-2 lock, pulls Step-4 work in.
- **Stateless servers:** referee owns the only `GameState`; servers receive context as call args. · Alternative rejected: per-server stateful inbox now — server state breaks the lock; NL content isn't due until Step 5.
- **Real HTTP transport for the run (§13 "separate ports"):** orchestrator is an HTTP client to **manually-started** servers. · Alternative rejected: in-memory `Client` only for the run — fails "separate ports," proves no networking (kept for **tests** only). · Deferred: spawning servers as subprocesses — nicer one-command demo but more orchestrator complexity; revisit at Step 7.
- **Minimal `GreedyMover` now:** meaningful demo without strategy. · Alternative rejected: full heuristic + Q-Table now — debugs strategy and networking together, collapses Step 4.
- **Limitation:** agents emit free-text messages but do **not** act on them; `observe()` records ground truth (full visibility). These are deliberate seams filled in Step 5, not bugs.
- **Config:** one **optional, operational** key `output.run_dir` (default `"runs"`) may be added as a trailing optional `Config` field (mirrors how `servers` was added). It is not a game parameter, so defaulting does not violate no-hard-coding of game values.

## 5. Success criteria & test scenarios (§2.3)
- **R-AC1** — End-to-end run: with both servers started manually, `python -m src.orchestrator` connects over HTTP, plays a full `num_games` series, and prints a transcript + `SeriesResult` with group totals in the §4.4 `[30, 90]` band. → *scenario:* manual launch of both servers + orchestrator; eyeball totals.
- **R-AC2** — Validate-before-apply: every applied move was first validated by the side-to-move's server, provable from the transcript/log (no move bypasses the gateway). → *test:* `test_every_move_validated` asserts a gateway `validate_move` call precedes each applied ply.
- **R-AC3** — Engine parity on 3×3: the `GreedyMover` Cop **captures** the Thief within `max_moves`, and the referee's reported scores equal the engine's `score_sub_game`. → *test:* `test_greedy_cop_captures_3x3`.
- **R-AC4** — Message bus: every emitted envelope is delivered to the other agent and recorded; envelopes contain only `{from, turn, ts, text}` (no coordinate fields). → *test:* `test_message_bus_delivers`, `test_envelope_has_no_coords`.
- **R-AC5** — Tests run **port-free** via `InMemoryGateway`, include a **3×3 resizability** case, and the full suite (existing 39 + new) passes. → *test:* `pytest -q` green; no real sockets opened.
- **R-AC6** — No hard-coded grid/port/host literals in `src/orchestrator/`; servers-down run prints "start the servers first" and exits non-zero. → *test:* grep check + `test_friendly_failure` (mock refused ping).
- **R-AC7** — Replay log: a series writes `runs/<timestamp>.jsonl` with one valid-JSON line per ply; line count == plies and each line round-trips through `json.loads`. → *test:* `test_replay_log_roundtrip`.
- **R-AC8** — Telemetry: gateway records exactly one timing sample per tool call; boot ping + avg/p95 summary present. → *test:* `test_telemetry_one_sample_per_call`.
- **R-AC9** — Observation log: every ply records a per-agent view for both COP and THIEF; `view["self"]` matches ground truth and the schema (incl. `sees_opponent`/`opponent_pos`) is stable. → *test:* `test_observe_schema`.
- **R-AC10** — ASCII render: `render_board(state)` returns a grid string sized to `config.grid_size` showing `C`, `T`, `#`; a known 3×3 state renders correctly. → *test:* `test_render_board_3x3`.

## Non-goals
- The real strategy brain — tunable heuristics + Q-Table / learning → **Step 4**.
- Barrier *strategy* (when/where the Cop walls) → **Step 4**. (Step 3 wires/tests the `place_barrier` validation path but `GreedyMover` never places barriers.)
- Natural-language understanding / location inference / deception → **Step 5** (Step-3 messages are free-text but agents don't act on them).
- Stateful server tools (`get_state`/`apply_move`/`inbox`/`reset`) — referee stays authoritative; servers stay stateless.
- Auto-launching servers as subprocesses (manual start chosen); cloud deploy / public URLs / tokens → **Step 7**.
- **Consuming** the instrumentation: GUI that *replays* JSONL → Step 6; Gmail report that *reads* it → Step 8; acting on the observation log → Step 5. Step 3 only **produces** these records.
