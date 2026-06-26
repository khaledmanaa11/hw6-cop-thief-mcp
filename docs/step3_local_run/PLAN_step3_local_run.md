# PLAN — Step 3: Full local run

- **Status:** triplet-built
- **Source:** `DECISION_step3_local_run.md`, `PRD_step3_local_run.md`
- **Cross-links:** `PRD_step3_local_run.md` (requirements) · `TODO_step3_local_run.md` (atomic build order)

## 1. Architecture (C4 / the seam)
A new **orchestrator / referee tier** sits in front of the two Step-2 servers. The referee owns the
only ground-truth `GameState` and mirrors the Step-1 `engine.play_sub_game` / `play_series` loop, but
inserts one extra hop per ply: it asks the **side-to-move's server** to `validate_move` over the wire
*before* it applies the move locally with the Step-1 engine. The single thing that makes this testable
without sockets is the **`ServerGateway` protocol**: the referee speaks only to the protocol, and we
plug in `HttpGateway` (real ports, for the run) or `InMemoryGateway` (no sockets, for tests). The four
instrumentation seams live in `recorders.py` so the loop stays readable; telemetry is captured inside
the gateway so it works identically for both transports.

```
   python -m src.orchestrator (the RUN)                 tests/test_orchestrator/ (PORT-FREE)
                 │                                                    │
        HttpGateway(url)  ── HTTP ──►  cop_server  :8001    InMemoryGateway(build_cop_server(config))
        HttpGateway(url)  ── HTTP ──►  thief_server:8002    InMemoryGateway(build_thief_server(config))
                 │                                                    │
                 └────────────────────┬───────────────────────────────┘
                                      ▼   (referee speaks ONLY to the protocol)
                         src/orchestrator/referee.py
                         ── owns ground-truth GameState ──
                         per ply: mover.choose_move → gateway.validate_move
                                  → engine.apply_move (local) → gateway.send_message
                                  → recorders (transcript / replay / observe / render)
                                      │ reuses, never re-implements
                                      ▼
              src/game/{engine,state,moves,rules,board,config,movers}.py  (Step-1 engine)
```

The gateway is the **seam**; the engine is **reused**; the recorders are **side-channels**. The only
genuinely new behavior in Step 3 is "validate over the wire before applying" and "route a message."

## 2. Public interface (stable contract)
```python
# src/orchestrator/gateway.py
class ServerGateway(Protocol):                       # what referee depends on
    async def ping(self) -> dict: ...
    async def validate_location(self, pos, barriers) -> dict: ...
    async def validate_move(self, to_move, cop_pos, thief_pos,
                            cop_barriers_left, barriers, move) -> dict: ...
    async def place_barrier(self, pos, cop_barriers_left, barriers) -> dict: ...
    async def send_message(self, envelope: dict) -> dict: ...

class HttpGateway:      # __init__(self, url: str, name: str, telemetry: Telemetry)
class InMemoryGateway:  # __init__(self, server, name: str, telemetry: Telemetry)
# both wrap fastmcp Client; every method returns result.data (the {ok, reason, …} dict)

# src/orchestrator/referee.py
async def run_sub_game(config, cop_gateway, thief_gateway,
                       cop_mover, thief_mover, recorders) -> SubGameResult: ...
async def run_series(config, cop_gateway, thief_gateway,
                     group_a, group_b, recorders) -> SeriesResult: ...

# src/game/movers.py  (added alongside existing Mover / RandomMover)
class GreedyMover:
    def choose_move(self, state: GameState) -> Move: ...   # role-aware Chebyshev pursue/evade
```

## 3. Data model / key structures
- **Message envelope** (unchanged from Step 2): `{ "from": str, "turn": int, "ts": str, "text": str }` — free text only, **no coordinate fields**.
- **Per-ply record (ONE shape, shared by the in-memory transcript and each JSONL line):**
  `{ turn, side, move, verdict: {ok, reason}, message: <envelope>, cop_score?, thief_score?, obs: {COP: <view>, THIEF: <view>}, ground_truth: {cop_pos, thief_pos, barriers, moves_used} }`.
  Build the dict **once per ply**: append to the transcript and write the same dict as a JSONL line — never diverge the two.
- **Observation view** (`observe(state, side) -> dict`): `{ "self": pos, "sees_opponent": bool, "opponent_pos": pos|null, "last_msg": str|null, "barriers": [...] }`. Step-3 policy records ground truth (full visibility); `sees_opponent`/`opponent_pos` are the fields Step 5 tightens to partial observability — present now even though always true today.
- **Telemetry:** per-call `(tool_name, ms)` samples + summary `{ calls, avg_ms, p95_ms, boot_ping: {cop_ms, thief_ms} }`.
- **Reused unchanged:** `GameState`, `Move` (king-move deltas), `SubGameResult`, `SeriesResult`, `apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`, and the §4.4 role-swap from `engine.play_series`.
- **Config:** new optional trailing field `Config.output_run_dir: str = "runs"` (parsed from an `output:` block if present, else default). Default keeps every existing positional `Config(...)` valid — same backward-compatible pattern as `servers`.

## 4. File layout (each ≤150 lines, §3.2)
- `src/orchestrator/__init__.py` (new) — make `src.orchestrator` importable.
- `src/orchestrator/gateway.py` (new) — `ServerGateway` protocol + `HttpGateway` (wraps `fastmcp.Client(url)`) + `InMemoryGateway` (wraps `Client(server_obj)`); each method `call_tool`s and returns `.data`; timing wrapped here.
- `src/orchestrator/referee.py` (new) — `run_sub_game` / `run_series`; reuses engine rules + `apply_move`; builds the per-ply record, routes messages, calls recorders. Written against the **protocol** only.
- `src/orchestrator/recorders.py` (new) — the 4 seams as small isolated units: `ReplayLog` (append-only JSONL writer to `output_run_dir`), `Telemetry` (per-call latency + boot-ping summary), `observe(state, side) -> dict`, `render_board(state) -> str`.
- `src/orchestrator/__main__.py` (new) — load config; build two `HttpGateway`s from `config.servers`; `ping` both (telemetry + friendly error + non-zero exit on refusal); `asyncio.run(run_series(...))`; stream ASCII board/transcript; write JSONL; print `SeriesResult` + telemetry summary.
- `src/game/movers.py` (edit) — add `GreedyMover` (alongside existing `Mover`/`RandomMover`).
- `src/game/config.py` (edit) — add optional `output_run_dir` field + conditional `output:` parsing.
- `config.yaml` (edit) — add optional `output: { run_dir: "runs" }`.
- `.gitignore` (edit) — add `runs/`.
- `tests/test_orchestrator/__init__.py` (new) + test modules (new) — port-free via `InMemoryGateway`, one test per instrumentation seam (see TODO coverage matrix).

## 5. ADRs — decision + rationale + alternatives (§2.2)
- **ADR-1 — `ServerGateway` protocol with two implementations.** · Rationale: one seam lets prod (HTTP) and tests (in-memory) share ONE referee; parity is what makes the loop trustworthy and fast to test. · Rejected: referee talks to `fastmcp.Client` directly — couples the loop to a transport and forces real sockets in tests.
- **ADR-2 — Validate-before-apply, referee applies locally.** · Rationale: honors the Step-2 stateless-server lock and §13's "separate ports" via real HTTP, with no rule duplication. · Rejected: stateful `apply_move` on the server — duplicates referee authority, contradicts Step-2 design.
- **ADR-3 — Telemetry inside the gateway (wrap `call_tool`).** · Rationale: both transports feed the same `Telemetry`; the referee needs zero timing code; in-memory ≈ 0 ms is fine — the HTTP path proves real network cost. · Rejected: timing in the referee — duplicates code and pollutes the loop.
- **ADR-4 — Recorders separate from the loop, ONE shared per-ply record.** · Rationale: each seam (`ReplayLog`/`Telemetry`/`observe`/`render_board`) is small and unit-testable; building the record once guarantees transcript and JSONL never diverge (the spine Steps 6/8 read). · Rejected: inline recording in `referee.py` — bloats the file past 150 lines and risks transcript/log drift.
- **ADR-5 — Single role-aware `GreedyMover`, Chebyshev metric.** · Rationale: moves are 8-directional king moves, so Chebyshev distance = minimum move count → correct greedy metric; one class branches on `state.to_move`. Deterministic tie-break (fixed `Move` order, no RNG) ⇒ reproducible demo + replay. · Rejected: separate Cop/Thief movers or RNG tie-break — more surface, non-reproducible logs.
- **ADR-6 — `output.run_dir` optional with default.** · Rationale: operational (not a game value), so defaulting is allowed; trailing optional field keeps Step-1 positional `Config(...)` construction valid. · Rejected: a required key — would break existing tests and conflate operational with game config.

## 6. Concurrency / gatekeeper / config notes
- **Async model:** the referee loop and gateways are `async`; `__main__` uses `asyncio.run`. The §4.4 role-swap is copied from `engine.play_series` but `await`s server-routed sub-games. No shared mutable state across concurrent tasks — sub-games run sequentially; the referee is single-threaded over `asyncio`, so no locking needed (§15 not triggered this step).
- **Gateway as the only network boundary:** all server I/O goes through `ServerGateway` (the §5.1 gatekeeper analog for tool calls); the referee makes no raw HTTP calls. Friendly failure (ping-then-exit) lives in `__main__`, not the loop.
- **Config-driven (§7.2):** host/ports from `config.servers`; grid bounds from `config.grid_size`; run dir from `config.output_run_dir`. No `5` / `8001` / `8002` literals anywhere in `src/orchestrator/`.
- **fastmcp client-over-HTTP API — VERIFY LIVE (context7) before writing code:** confirm the URL/path (e.g. `http://host:port/mcp`) and that `async with Client("http://host:port/…") as c: (await c.call_tool(name, {...})).data` returns the same dict the in-memory `Client(server)` does. That parity is the load-bearing assumption behind ADR-1. *(Server side already confirmed in Step 2: `FastMCP`, `@mcp.tool`, `mcp.run(transport="http", host, port)`, `result.data`.)*
- **Engine reuse, not re-implementation:** import `apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`, `SubGameResult`, `SeriesResult` from Step 1. `GreedyMover` excludes `Move.PLACE_BARRIER` from its candidates.
