# DECISION — Step 1: Game Logic & Rules

- **Roadmap position:** step 1 of 8 (`step1_game_logic`)
- **Date discussed:** 2026-06-25
- **Status:** decision-written
- **Assignment references:** §3 (mission), §4.1 (sub-game/game structure), §4.2 (board), §4.3 (win conditions & barriers), §4.4 (scoring, Table 1), §4.5 (sanity ladder)

## 1. What this step is (one paragraph)
A pure, standalone Python game engine for the Cop & Thief pursuit game. It knows the
rules of the game and acts as the referee: it builds a resizable grid, places the two
players and barriers, validates and applies moves turn by turn, detects capture and
timeout, computes scores, and runs both a single sub-game and a full series of 6
sub-games. It contains **no MCP, no LLM, no networking, and no GUI** — moves are fed in
through a pluggable interface. This is the foundation every later step plugs into.

## 2. What it adds to the project
- `config.yaml` — the single source of truth for every game parameter (no hard-coding anywhere else).
- A `src/game/` Python package that can play a full 6-sub-game series end-to-end from the command line with random players.
- A typed config loader, a resizable board with barriers, a game-state snapshot, move legality checking, win/score rules, and a referee loop.
- A `choose_move(state) -> Move` move-provider seam (with a `RandomMover`) that Steps 2–4 plug into without touching the engine.
- A structured **result object** per sub-game and per series (winner, scores, move count) — the exact data Step 8's JSON email and Step 6's GUI will later consume.
- A test suite proving the rules across the 2×2 → 3×3 → 4×4 → 5×5 sanity ladder.

## 3. Scope
**In scope:**
- Grid, movement (8-directional incl. diagonals), barriers, capture, timeout, scoring.
- Turn-based loop (Thief first), sub-game loop, 6-sub-game series loop with score accumulation.
- `config.yaml` + validated loader.
- Pluggable move provider + a `RandomMover`.
- Tests across all four sanity-ladder grid sizes.

**Out of scope (deferred):**
- MCP servers / FastMCP tools → step 2.
- Wiring agents+servers on localhost → step 3.
- Any strategy / decision brain (heuristic / Q-Table) → step 4. (`RandomMover` is the placeholder.)
- Natural-language messaging between agents → step 5.
- GUI → step 6. Cloud deploy → step 7. Gmail JSON report → step 8.

## 4. Chosen approach (and what we rejected)
**Decision:** A small, layered pure-Python package (`config → board → state → moves → rules → movers → engine`) driven entirely by `config.yaml`, with moves supplied through a `choose_move(state)` interface.

**Why:** Keeping the engine pure and config-driven satisfies the assignment's hard constraints (resizable board, no hard-coding) and isolates the graded orchestration concerns to later steps. The move-provider seam means the engine never changes when the MCP agents (step 3) or the decision brain (step 4) arrive.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Pure engine + pluggable move provider | ✅ chosen | Clean seam for steps 2–4; testable in isolation; honors no-hard-coding. |
| Engine with a built-in random/heuristic mover only | ❌ rejected | Would force an engine refactor when the brain/agents arrive. |
| Bake MCP/LLM hooks into the engine now | ❌ rejected | Violates the layering; engine must stay pure (server/client split, §5). |
| 8-full-rounds move counting | ❌ rejected | PDF says "at most 25 moves"; literal reading is 25 plies. |

## 5. Dependencies & interfaces
- **Consumes from prior steps:** none (this is step 1).
- **Exposes to later steps:**
  - `choose_move(state) -> Move` — the interface MCP agents (step 3) and the decision brain (step 4) implement.
  - `GameState` snapshot — what a mover reads to decide.
  - `SubGameResult` (winner role, per-role scores, move count, and which group played each role) / `SeriesResult` (per-game results + each group's total) — consumed by the GUI (step 6) and the JSON email (step 8).
  - `config.yaml` schema — the parameter contract all steps share.
- **Touches config keys:** `grid_size`, `max_moves`, `num_games`, `max_barriers`, `scoring.cop_win`, `scoring.thief_win`, `scoring.cop_loss`, `scoring.thief_loss`.

## 6. Binding constraints (from the assignment)
- **Board must be resizable** — generic architecture, never assume 5×5 (§4.2).
- **No hard-coding** — all parameters from `config.yaml` (cross-cutting).
- **Engine stays pure** — no LLM, no MCP in this layer; the LLM lives in the client/orchestrator later (§5, §5.2).
- **Free-NL future-proofing** — the move-provider seam must not assume a fixed coordinate protocol, so step 5's free-text agents fit the same interface.

## 7. Key design decisions
- **Files/modules:**
  - `config.yaml` (repo root)
  - `src/game/__init__.py`
  - `src/game/config.py` — load + validate YAML into a typed config object.
  - `src/game/board.py` — grid + barriers; `in_bounds`, `is_blocked`, `place_barrier`.
  - `src/game/state.py` — `GameState` snapshot (positions, turn, moves_used, barriers_left).
  - `src/game/moves.py` — the 8 directions + barrier action; `legal_moves(state)`, `is_legal(state, move)`.
  - `src/game/rules.py` — `is_capture(state)`, `is_timeout(state)`, `score(result, config)`.
  - `src/game/movers.py` — `Mover` protocol `choose_move(state) -> Move`; `RandomMover`.
  - `src/game/engine.py` — `play_sub_game(...) -> SubGameResult`; `play_series(...) -> SeriesResult`.
  - `tests/test_game/` — across 2×2, 3×3, 4×4, 5×5.
- **Core data structures:**
  - `Position = (row, col)`.
  - `Move` — a direction enum value, or a `PLACE_BARRIER` action (Cop only).
  - `GameState` — `cop_pos`, `thief_pos`, `to_move` (THIEF|COP), `moves_used`, `cop_barriers_left`, board reference.
  - `SubGameResult` — `winner`, `cop_score`, `thief_score`, `moves_used`.
  - `SeriesResult` — list of `SubGameResult` + accumulated `cop_total`, `thief_total`.
- **Key signatures (intent):**
  - `load_config(path) -> Config` — parse + validate; reject illegal grids/scores.
  - `legal_moves(state) -> list[Move]` — bounds + barrier aware; includes barrier action for Cop if barriers remain.
  - `apply_move(state, move) -> GameState` — returns the next state (new snapshot).
  - `play_sub_game(config, cop_mover, thief_mover) -> SubGameResult` — Thief-first turn loop, capped at `max_moves` plies.
  - `play_series(config, cop_mover, thief_mover) -> SeriesResult` — runs `num_games` sub-games, accumulates scores.

## 8. Acceptance criteria (how we know the step is done)
1. `play_series` runs end-to-end on a default 5×5 config with two `RandomMover`s and returns a `SeriesResult` of 6 sub-games with accumulated scores.
2. The same code runs unchanged on 2×2, 3×3, and 4×4 grids (resizable proven; no hard-coded 5).
3. A Cop landing on the Thief's cell ends the sub-game with Cop win → Cop 20 / Thief 5.
4. A sub-game reaching 25 plies with no capture ends with Thief win → Cop 5 / Thief 10.
5. A barrier placed by the Cop makes that cell impassable to both players, the action consumes the Cop's turn, and the Cop is hard-capped at `max_barriers` (5) per sub-game; the Thief can never place one.
6. Movement is 8-directional incl. diagonals; out-of-bounds and into-barrier moves are rejected.
7. Every parameter comes from `config.yaml`; grepping the source for literal `5`, `25`, `6`, `20`, `10` as game values finds none.
8. Series total respects the 90-max / 30-min bound from §4.4.

## 9. Resolved questions / open items
- **Q:** Movement directions? → **A:** 8-directional including diagonals (§4.2).
- **Q:** Turn order? → **A:** Turn-based, **Thief moves first**, then Cop, repeat (§4.1).
- **Q:** What is "25 moves"? → **A:** 25 **plies** — each single player turn counts as one move (Director's call).
- **Q:** Capture condition? → **A:** Cop occupies the **exact same cell** as the Thief (§4.3).
- **Q:** Barriers? → **A:** Cop only; placed on the Cop's **current cell** as an alternative to moving (consumes the turn); cell becomes impassable to **both**; **max 5** per sub-game (§4.3).
- **Q:** Config format / move source? → **A:** `config.yaml`; pluggable `choose_move(state)` move provider with a `RandomMover` placeholder.
- **Q:** How does the 6-sub-game series score map to the §4.4 "90 max / 30 min per group"? → **A:** (resolved post-build) The two **groups swap Cop/Thief roles** every sub-game — each plays Cop 3× and Thief 3× — and a group's series total is its Cop points + its Thief points. `play_series(config, group_a, group_b)` implements this. Without the swap, a fixed-role side could reach 120, violating the 90 bound.
- **Still open (note for Builder):** none — all rules sourced.

## 10. Notes for the Builder session
- Put the **most TODO detail** in `engine.py` (the turn loop + series loop) and `rules.py` (capture/timeout/scoring), since those encode the graded correctness of the game.
- Keep `movers.py` deliberately thin — it is a seam, not logic. The `Mover` protocol signature is the contract steps 3–5 depend on; do not change its shape.
- Every test must be parameterized over grid size (2×2 … 5×5) to prove resizability, not just run on 5×5.
- No literal game numbers in code — pull everything from the `Config` object. A test that greps for stray literals is welcome.
- The `SubGameResult` / `SeriesResult` shapes are a downstream contract (steps 6 and 8). Make them plain, serializable data (dataclasses), not behavior-bearing objects.
