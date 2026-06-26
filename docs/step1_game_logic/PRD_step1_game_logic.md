# PRD — Step 1: Game logic & rules

- **Status:** triplet-built
- **Source:** `DECISION_step1_game_logic.md`
- **Assignment references:** §3, §4.1–§4.5

## 1. Problem & context
A pure Python game engine for the Cop & Thief pursuit game must exist before any MCP, agent, or UI layers are added. This engine is the referee: it builds a resizable board, enforces movement and barrier rules, detects capture and timeout, computes scores, and runs a series of 6 sub-games. It also exposes a pluggable mover interface so future steps can plug in Cop and Thief decision logic without changing the engine.

## 2. Goal & success metric
Build a config-driven engine that can execute a full 6-sub-game series end-to-end, returning structured sub-game and series results. Success is measured by a working `play_series` path on default 5×5 config plus passing tests on 2×2, 3×3, 4×4, and 5×5 grids.

## 3. Stories
- As the **game engine**, I need to enforce grid bounds, barriers, capture, timeout, and scoring so that each sub-game resolves correctly.
- As the **Cop mover**, I need a `choose_move(state)` interface so the MCP-backed Cop can later replace the placeholder mover without engine changes.
- As the **orchestrator**, I need plain `SubGameResult` and `SeriesResult` objects so aggregated results can later be consumed by the GUI and JSON reporting.
- As the **test harness**, I need explicit grid-size escalation so the engine proves it is resizable and not hard-coded to 5×5.

## 4. Functional requirements
- **FR1** — `config.yaml` must define `grid_size`, `max_moves`, `num_games`, `max_barriers`, `scoring.cop_win`, `scoring.thief_win`, `scoring.cop_loss`, and `scoring.thief_loss`, and the engine must load and validate these values.
- **FR2** — The board must support arbitrary dimensions from `config.yaml`, and movement into out-of-bounds cells must be rejected.
- **FR3** — Movement must support 8 directions including diagonals.
- **FR4** — The Cop wins when it occupies the same cell as the Thief; this ends the sub-game immediately.
- **FR5** — A sub-game that reaches `max_moves` plies without capture ends as a Thief win.
- **FR6** — The Cop may place a barrier instead of moving, barriers are impassable to both players, and the Cop may not exceed `max_barriers` per sub-game.
- **FR7** — The engine must remain pure Python with no MCP, networking, or LLM logic inside this step.
- **FR8** — `play_series` must run `num_games` sub-games between two **groups**, swapping Cop/Thief roles each sub-game so each group plays Cop in half and Thief in half, and aggregate **each group's** total (its Cop points + its Thief points) — per §4.4.

## 5. Non-functional requirements
- **NFR1 — config-driven:** all game parameters must be read from `config.yaml`.
- **NFR2 — resizable:** the engine must work for arbitrary grid dimensions and not assume a fixed 5×5 board.
- **NFR3 — pure separation:** no MCP or LLM logic may be introduced in this engine layer.
- **NFR4 — testable:** the system must support unit and integration tests for rules and series execution.

## 6. In scope / Out of scope
**In scope:** config loading, board representation, game state snapshot, legal moves, cop barrier placement, capture detection, timeout detection, scoring, series runner, `RandomMover` placeholder, and parameterized tests across 2×2 to 5×5.

**Out of scope:** MCP server infrastructure → step 2, local orchestration wiring → step 3, decision/strategy brain → step 4, natural-language agent messaging → step 5, graphical UI → step 6, cloud deployment → step 7, Gmail JSON reporting → step 8.

## 7. Acceptance criteria
1. `play_series` runs end-to-end on the default 5×5 config with two group `RandomMover` instances and returns a `SeriesResult` containing 6 sub-game results and each group's accumulated total.
2. The same code runs unchanged on 2×2, 3×3, 4×4, and 5×5 grids.
3. A Cop move that lands on the Thief ends the sub-game with Cop score `scoring.cop_win` and Thief score `scoring.thief_loss`.
4. A sub-game that reaches `max_moves` plies ends with Thief score `scoring.thief_win` and Cop score `scoring.cop_loss`.
5. Cop barrier placement renders a cell impassable to both players, consumes the Cop's turn, and is limited by `max_barriers` per sub-game.
6. Illegal out-of-bounds or barrier-cell moves are rejected.
7. No hard-coded game parameters appear in engine code; all values come from `config.yaml`.
8. Because roles swap each sub-game, each group's series total respects the 90-max / 30-min bound from §4.4.

## 8. Dependencies
- **Upstream (needs):** none — this is the first step.
- **Downstream (unblocks):** step 2 — `choose_move(state)` interface and result object contract; step 3 — local series execution without MCP changes.

## 9. References
- Assignment §3, §4.1, §4.2, §4.3, §4.4, §4.5
- `DECISION_step1_game_logic.md`
- `config.yaml` keys: `grid_size`, `max_moves`, `num_games`, `max_barriers`, `scoring.cop_win`, `scoring.thief_win`, `scoring.cop_loss`, `scoring.thief_loss`
