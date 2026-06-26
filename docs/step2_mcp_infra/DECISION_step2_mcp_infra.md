# DECISION — Step 2: Basic MCP Infrastructure

- **Roadmap position:** step 2 of 8 (`step2_mcp_infra`)
- **Date discussed:** 2026-06-25
- **Status:** decision-written
- **Assignment references:** §5 (server/client split — LLM in client, MCP server exposes tools), §5.2 (FastMCP), §6 (free natural-language messaging — design must allow it), §10/§13 (roadmap step 2), cross-cutting (no hard-coding, resizable board, Dec-POMDP).

## 1. What this step is (one paragraph)
Stand up the **two separate FastMCP servers** — one for the Cop agent, one for the
Thief agent — each advertising its tool list and answering tool calls **in isolation**.
This is **plumbing only**: the servers are thin, stateless wrappers over the Step-1 game
engine that expose mechanical, deterministic services (legality checks, a free-text
message intake, a health probe). There is **no game loop, no strategy/brain, and no LLM**
in this step — those arrive in Steps 3, 4 and 5. The deliverable is two running server
processes whose every tool is proven by tests through an MCP client.

## 2. What it adds to the project
- A `src/mcp_servers/` package with **two FastMCP servers**: `cop_server.py` and `thief_server.py`.
- A shared **tool contract** (`tools.py`) that both servers build on — thin adapters that call the existing engine primitives (`legal_moves`, `apply_move`-adjacent checks, board bounds/barriers).
- **HTTP (streamable-http) transport**, each server bound to its own **config-driven host/port** (no hard-coded ports).
- New `config.yaml` keys for server host/ports (single source of truth, no hard-coding).
- A test suite that, using FastMCP's **in-memory `Client`**, calls every tool on each server and asserts the response — proving the plumbing without real sockets.
- Three forward-looking design seams baked into the contract (rich `reason` returns, a free-text-only message envelope, a partial-observation seam) so Steps 4–5 plug in without reshaping the API.

## 3. Scope
**In scope:**
- Two FastMCP server objects (Cop, Thief), each with its tool set registered.
- Tools (this step): `ping`, `validate_location`, `validate_move`, `send_message` (both servers); `place_barrier` **validation** (Cop server only).
- streamable-http transport; host + ports read from `config.yaml`.
- A small CLI/entrypoint to launch each server (`python -m src.mcp_servers.cop_server`, `…thief_server`).
- In-memory-client tests for every tool on every server.

**Out of scope (deferred):**
- Wiring the engine + both agents + both servers into a running series → **step 3**.
- A referee/orchestrator that holds the live `GameState` and drives turns → **step 3**.
- `apply_move` / `make_move` / `get_state` as *behavioral* tools (mutating real game state) → **step 3**.
- Any strategy / decision brain → **step 4**.
- LLM reasoning, free-text inference/deception (the message body is carried but not *interpreted*) → **step 5**.
- GUI → 6; cloud deploy/tokens/public URLs → 7; Gmail JSON report → 8.

## 4. Chosen approach (and what we rejected)
**Decision:** Two **symmetric-by-default, stateless** FastMCP servers built on a shared
tool module, over **HTTP (streamable-http) on config-driven ports**, using the
**standalone `fastmcp`** package. Ground-truth game state is **owned by the referee/client
(Step 3)** — the servers hold no game state; state-dependent tools take what they need as
arguments.

**Why:** Stateless servers keep Step 2 pure plumbing (no two-copies-of-the-board sync
problem), honor the assignment's "LLM/brain in the client, server exposes tools" rule, and
make every tool trivially testable in isolation. HTTP-on-ports is what Step 3 (localhost,
two ports) and Step 7 (cloud public URLs) both need, so there is no throwaway transport.
The standalone `fastmcp` is a maintained superset of the SDK's bundled (frozen 1.0)
FastMCP and ships the in-memory `Client` the tests rely on.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Referee owns state; servers stateless | ✅ chosen | No state-sync bugs; matches LLM-in-client; trivial isolated tests. |
| Each server holds its own board view | ❌ rejected | Two states to keep consistent; drags Step 4/5 concerns into Step 2. |
| HTTP (streamable-http) on config ports | ✅ chosen | Ready for Step 3 (two localhost ports) and Step 7 (cloud URLs), no rework. |
| stdio transport now, HTTP later | ❌ rejected | Throwaway; would force re-plumbing for Step 3/7. |
| Standalone `fastmcp` (3.x) | ✅ chosen | Maintained superset; provides in-memory `Client` for clean tests. |
| `mcp` SDK's bundled `FastMCP` (1.0) | ❌ rejected | Frozen at 1.0; no client → tests forced over real sockets. |
| Expose `apply_move`/`get_state` as tools now | ❌ rejected | That is Step 3's wiring; keep Step 2 plumbing-only. |

## 5. Dependencies & interfaces
- **Consumes from prior steps (Step 1):**
  - `Config` (incl. `grid_size`, `max_barriers`) from `src/game/config.py`.
  - `Board` bounds/barrier checks, `GameState`, `legal_moves(state)`, `Move` and move legality from `src/game/{board,state,moves}.py`. Tools are **adapters** over these — no game rules are re-implemented in the server layer.
- **Exposes to later steps:**
  - The **tool contract** (names, argument shapes, `{ok, reason}` return shape, message envelope) that the Step-3 orchestrator/agents will call over MCP.
  - Two launchable server entrypoints on known config ports.
- **Touches config keys:** **adds** a `servers:` block — `servers.cop.host`, `servers.cop.port`, `servers.thief.host`, `servers.thief.port`. Reuses `grid_size`, `max_barriers` for validation. Defaults: host `127.0.0.1`, Cop port `8001`, Thief port `8002`.

## 6. Binding constraints (from the assignment)
- **LLM/brain lives in the client, not the server** (§5): server tools are mechanical and deterministic only. No `suggest_move`/`evaluate_position`-type tools — those are client logic.
- **No hard-coding** (cross-cutting): ports/host and all game parameters come from `config.yaml`.
- **Resizable board**: validation tools derive bounds from `Config.grid_size`, never a literal 5.
- **Free natural language must be allowed** (§6): `send_message` carries an **opaque free-text body with no coordinate fields** in its schema, so Step 5 needs no contract change.
- **Dec-POMDP future-proofing**: the observation surface is designed as **per-agent partial views**, not one omniscient state dump, so the README's ⟨Ωᵢ, O⟩ model is real later.

## 7. Key design decisions
- **Files/modules (intended):**
  - `src/mcp_servers/__init__.py`
  - `src/mcp_servers/tools.py` — pure adapter functions over the engine; the shared contract both servers register.
  - `src/mcp_servers/cop_server.py` — builds the Cop `FastMCP` instance (registers shared tools **+ `place_barrier` validation**); `__main__` launches it via config host/port.
  - `src/mcp_servers/thief_server.py` — builds the Thief `FastMCP` instance (shared tools only); `__main__` launches it.
  - `tests/test_mcp/` — in-memory `Client` tests per server, per tool.
  - `config.yaml` — add the `servers:` block.
- **The Step-2 tool contract:**
  - `ping() -> {ok: true, server: "cop"|"thief"}` — liveness (needed for Step 7).
  - `validate_location(pos) -> {ok: bool, reason: str}` — on-board and not a barrier.
  - `validate_move(move) -> {ok: bool, reason: str}` — legal under 8-dir + barrier rules.
  - `send_message(envelope) -> {ok: bool, reason: str}` — accept a free-text message (ack/echo only in Step 2; not interpreted).
  - `place_barrier(pos) -> {ok: bool, reason: str}` — **Cop server only**, **validation only** (would-this-be-legal); does not mutate real state in Step 2.
- **Core shapes:**
  - **Result shape:** every tool returns `{ ok: bool, reason: str, ... }` — rich, human-readable `reason` strings (e.g. `"blocked: barrier at (2,3)"`), never a bare bool.
  - **Message envelope:** `{ from: str, turn: int, ts: str, text: str }` — `text` is opaque free natural language; **no coordinate fields in the schema**.
  - **Partial-observation seam:** observation tools are scoped per agent (`get_my_position` / `get_opponent_position` shape reserved for Step 3/5) rather than a single `get_state` dump — decided now, implemented later.
- **State handling:** servers are **stateless**; any tool needing board state receives the needed inputs as arguments. The authoritative `GameState` lives in the Step-3 referee/client.

## 8. Acceptance criteria (how we know the step is done)
1. `python -m src.mcp_servers.cop_server` and `…thief_server` each start a FastMCP server bound to the **config-driven** host/port (Cop 8001, Thief 8002 by default) with no errors.
2. Via FastMCP's in-memory `Client`, calling `ping` on each server returns `{ok: true, server: …}` identifying the correct server.
3. `validate_location` / `validate_move` return `{ok, reason}` with a **non-empty human-readable `reason`**, and their verdicts agree with the Step-1 engine (a move the engine calls legal is `ok: true`; an off-board or into-barrier one is `ok: false` with a descriptive reason).
4. `send_message` accepts an envelope whose `text` is arbitrary free natural language and returns an ack; the **schema contains no coordinate fields**.
5. The **two servers are asymmetric**: `place_barrier` exists on the Cop server and is **absent** on the Thief server (a Thief-side call fails / tool not found).
6. All validation derives bounds from `Config.grid_size`; running the tests against a 3×3 config (not just 5×5) passes unchanged — **resizability proven**.
7. No hard-coded ports or game numbers in `src/mcp_servers/` — all from `config.yaml`/`Config`.
8. Every tool on every server has at least one passing in-memory-client test; the existing Step-1 suite still passes.

## 9. Resolved questions / open items
- **Q:** Where does ground-truth game state live? → **A:** The **referee/client (Step 3)** owns the single `GameState`; Step-2 servers are **stateless** tool faces.
- **Q:** Transport? → **A:** **HTTP (streamable-http)** on **config-driven ports** (Cop 8001 / Thief 8002, host 127.0.0.1) — ready for Step 3 and Step 7.
- **Q:** Which FastMCP? → **A:** The **standalone `fastmcp`** package (3.x), not the `mcp` SDK's bundled 1.0 — maintained superset, gives the in-memory `Client` for tests.
- **Q:** Which tools in Step 2? → **A:** `ping`, `validate_location`, `validate_move`, `send_message` (both); `place_barrier`-validate (Cop only). Everything else (`get_state`, `apply_move`, inbox, scoring, reset) is **deferred to Step 3+**.
- **Q:** Where is the Director's creativity in this (otherwise mechanical) step? → **A:** Three contract-level design seams, **locked**: (1) rich `{ok, reason}` returns, (2) free-text-only message envelope, (3) partial-observation seam. These shape Steps 4–5 expressiveness at zero Step-2 cost.
- **Still open (note for Builder):** none — confirm the exact `fastmcp` run/transport call against the live `fastmcp` docs when writing the TODO (API surface for `mcp.run(transport="http", host=…, port=…)` and `Client(server)` may need a doc check).

## 10. Notes for the Builder session
- Keep `tools.py` as **pure adapters**: each tool delegates to the Step-1 engine and re-shapes the result into `{ok, reason}`. Do **not** re-implement any game rule in the server layer — call `legal_moves` / bounds / barrier checks.
- Put the **most TODO detail** in the tool contract: exact argument schemas, the `{ok, reason}` shape, the message-envelope fields, and what a "good" `reason` string reads like (give 2–3 example strings per tool).
- The **asymmetry** (Cop has `place_barrier`, Thief does not) is a deliberate, testable design point — call it out in the TODO and add the negative test (Thief lacks the tool).
- Servers must be **stateless** — no module-level game state. If a tool needs the board, it takes the inputs as arguments.
- All ports/host from the new `config.yaml` `servers:` block; tests must run against a non-5×5 grid to prove resizability.
- Verify the precise `fastmcp` API (server construction, `@mcp.tool`, `mcp.run(...)` transport args, in-memory `Client(server)` usage) against current `fastmcp` docs before finalizing box-level code — the API has moved across versions.
- Do **not** add `get_state`/`apply_move`/inbox/scoring tools here — they belong to Step 3 and adding them would break the "plumbing only" boundary.
