# PRD — Step 2: Basic MCP infrastructure

- **Status:** ✅ done — all acceptance criteria verified 2026-06-25 (39 tests pass, F2 grep clean, both servers build)
- **Source:** `DECISION_step2_mcp_infra.md`
- **Assignment references:** §5 (server/client split — LLM in client, MCP server exposes tools), §5.2 (FastMCP), §6 (free natural-language messaging must be allowed), §10/§13 (roadmap step 2)

## 1. Problem & context
The Step-1 engine is a pure-Python referee. Before any agent can *talk* to it over a network, the project needs the **MCP plumbing**: two separate FastMCP servers — one fronting the Cop agent, one fronting the Thief agent — that advertise a tool list and answer tool calls in isolation. This step builds **only that plumbing**: thin, **stateless** adapters over the Step-1 engine that expose mechanical, deterministic services (legality checks, a free-text message intake, a health probe). There is **no game loop, no strategy brain, and no LLM** here — those arrive in Steps 3, 4, 5. After this step the project has two launchable server processes whose every tool is proven by an in-memory MCP client.

## 2. Goal & success metric
Stand up `cop_server` and `thief_server` as FastMCP servers on **config-driven host/ports** (streamable-http), each exposing the Step-2 tool contract, with **every tool on every server covered by a passing in-memory-`Client` test**. Success = both servers start with no errors on the config ports, all tools return the agreed `{ok, reason, …}` shapes, the tool verdicts agree with the Step-1 engine, and the suite passes unchanged on a non-5×5 grid (resizability proven).

## 3. Stories
- As the **Cop agent's server face**, I need to expose `ping`, `validate_location`, `validate_move`, `send_message`, and `place_barrier`-validation tools so the Step-3 orchestrator can call them over MCP.
- As the **Thief agent's server face**, I need the same tools **except `place_barrier`** (the Thief cannot build walls), so the server asymmetry mirrors the game rules.
- As the **orchestrator (Step 3)**, I need a stable tool contract (`{ok, reason}` returns, an opaque free-text message envelope, per-agent observation seam) so I can wire the live game without reshaping the API.
- As the **test harness**, I need FastMCP's in-memory `Client` so I can call every tool without opening real sockets, and I need the tools to derive bounds from `Config.grid_size` so a 3×3 run proves resizability.

## 4. Functional requirements
- **FR1** — There are **two FastMCP server objects**, `cop` and `thief`, each launchable as a process: `python -m src.mcp_servers.cop_server` and `python -m src.mcp_servers.thief_server`.
- **FR2** — Each server binds to a **config-driven** host/port over **streamable-http** transport; no port or host literal appears in `src/mcp_servers/`.
- **FR3** — Both servers expose `ping`, `validate_location`, `validate_move`, and `send_message`. The Cop server **additionally** exposes `place_barrier` (validation only). The Thief server does **not** expose `place_barrier`.
- **FR4** — Every tool returns a structured result `{ ok: bool, reason: str, … }` with a **non-empty, human-readable** `reason`; `ping` also returns `server` identifying which server answered.
- **FR5** — `validate_location` and `validate_move` are **thin adapters** over the Step-1 engine (`Board` bounds/barrier checks, `legal_moves`); their verdicts must **agree with the engine** (a move the engine calls legal is `ok:true`; an off-board or into-barrier one is `ok:false`).
- **FR6** — `send_message` accepts an envelope whose body `text` is **arbitrary free natural language**; the tool's input schema carries **no coordinate fields** (its only parameter is the opaque `envelope`).
- **FR7** — `place_barrier` (Cop server only) **validates** whether placing a barrier would be legal (in-bounds, not a duplicate, budget remaining) and **does not mutate** any real game state.
- **FR8** — Servers are **stateless**: no module-level game state. Any tool needing board context receives it as call arguments.
- **FR9** — Every tool on every server has at least one passing in-memory-`Client` test, and the existing Step-1 suite still passes.

## 5. Non-functional requirements
- **NFR1 — config-driven:** host/ports come from a new `servers:` block in `config.yaml`; grid bounds come from `Config.grid_size` (no hard-coding).
- **NFR2 — resizable:** all bound checks derive from `Config.grid_size`; the test suite runs against a 3×3 config (not only 5×5) and passes unchanged.
- **NFR3 — server/client split:** server tools are mechanical and deterministic only — **no `suggest_move`/`evaluate_position`** (that is client/LLM logic for later steps).
- **NFR4 — no rule duplication:** the server layer never re-implements a game rule; it calls the Step-1 engine and re-shapes the result into `{ok, reason}`.
- **NFR5 — plumbing-only boundary:** `get_state`, `apply_move`, inbox, scoring, and reset tools are **not** added in this step.

## 6. In scope / Out of scope
**In scope:** `src/mcp_servers/` package; shared `tools.py` adapters; `cop_server.py` + `thief_server.py` builders & `__main__` launchers; a `servers:` block in `config.yaml` and its loader support; in-memory-`Client` tests for every tool on both servers; the three locked design seams (rich `{ok, reason}` returns, free-text-only envelope, per-agent observation seam noted for later).

**Out of scope:** wiring engine + agents + servers into a running series → step 3; a referee that holds the live `GameState` → step 3; `apply_move`/`get_state` as *behavioral* (state-mutating) tools → step 3; strategy/decision brain → step 4; LLM reasoning / free-text inference & deception → step 5; GUI → step 6; cloud deploy/tokens/public URLs → step 7; Gmail JSON report → step 8.

## 7. Acceptance criteria
1. `python -m src.mcp_servers.cop_server` and `python -m src.mcp_servers.thief_server` each start a FastMCP server bound to the **config-driven** host/port (Cop `127.0.0.1:8001`, Thief `127.0.0.1:8002` by default) with no errors. *(Verified: launch each, observe it binds the port; the build step is unit-tested without a live socket.)*
2. Via the in-memory `Client`, `ping` on each server returns `{ok: true, server: "cop"|"thief", …}` identifying the correct server. *(Verified: `test_ping_*`.)*
3. `validate_location` / `validate_move` return `{ok, reason}` with a **non-empty** `reason`, and verdicts agree with the Step-1 engine. *(Verified: `test_validate_location_*`, `test_validate_move_agrees_with_engine`.)*
4. `send_message` accepts an envelope whose `text` is arbitrary free natural language and returns an ack; the tool's **only input parameter is the opaque `envelope`** — no coordinate fields in the schema. *(Verified: `test_send_message_free_text`, `test_send_message_schema_has_no_coords`.)*
5. The two servers are **asymmetric**: `place_barrier` is present on the Cop server and **absent** on the Thief server. *(Verified: `test_asymmetry_place_barrier`.)*
6. All validation derives bounds from `Config.grid_size`; the suite run against a **3×3** config passes unchanged. *(Verified: `test_resizable_3x3`.)*
7. No hard-coded ports or game numbers in `src/mcp_servers/`. *(Verified: grep check in the final box.)*
8. Every tool on every server has ≥1 passing in-memory-`Client` test; the existing Step-1 suite still passes. *(Verified: `pytest -q` green.)*

## 8. Dependencies
- **Upstream (needs):** Step 1 — `Config`/`load_config` (`grid_size`, `max_barriers`), `Board` (`in_bounds`, `is_blocked`), `GameState`, `Move`, `legal_moves` from `src/game/`.
- **Downstream (unblocks):** Step 3 — the tool contract (names, arg shapes, `{ok, reason}` return, message envelope) and two launchable server entrypoints that the orchestrator/agents call over MCP.

## 9. References
- Assignment §5, §5.2, §6, §10, §13; `DECISION_step2_mcp_infra.md`
- New `config.yaml` keys: `servers.cop.host`, `servers.cop.port`, `servers.thief.host`, `servers.thief.port` (defaults `127.0.0.1` / `8001` / `8002`)
- Reused `config.yaml` keys: `grid_size`, `max_barriers`
- Library: standalone **`fastmcp`** (3.x) — `FastMCP`, `@mcp.tool`, `mcp.run(transport="http", host=…, port=…)`, in-memory `Client(server)`
