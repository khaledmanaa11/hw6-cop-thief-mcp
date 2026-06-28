# DECISION — Step 4: Decision Engine (strategy brain)

- **Roadmap position:** step 4 of 8 (`step4_decision_engine`)
- **Date discussed:** 2026-06-26
- **Status:** decision-written
- **Assignment references:** §2 (strategy is *recommendation only*, not graded — orchestration/communication is), §3 (central success metric = communication & orchestration of the agent pair, **not** the game-strategy algorithm; bonus competition up to 10 pts is separate), §4.1 (sub-game = ≤25 plies, Thief first), §4.2 (**movement is 8-directional incl. diagonals — mandatory**; board resizable via config; start positions may be random or strategically chosen), §4.3 (barriers: Cop walls its **own current cell** as an alternative to moving, costs the turn, impassable to both, max 5, Thief none), §4.4 (Table 1 scoring), §4.5 (sanity ladder 2×2→5×5), §8 (Tabular Q-Learning is **optional and recommended only**).

## 1. What this step is (one paragraph)
Step 4 replaces the Step-3 placeholder brain (`GreedyMover`, pure Chebyshev pursue/evade)
with a **real, config-selectable decision engine** behind the existing
`choose_move(state) -> Move` seam. It adds a **depth-limited minimax / alpha-beta**
strategist (the primary brain, for the bonus competition) and an **optional Tabular
Q-Learning** strategist (per §8), while keeping `GreedyMover` as a baseline/fallback.
Which brain drives the Cop and which drives the Thief is chosen entirely from
`config.yaml`. Movement stays 8-directional and barriers stay exactly as locked in
Step 1 (the assignment mandates both). After this step the project has agents that
*pursue and evade with genuine lookahead* and can be swapped/tuned without touching the
engine, the servers, or the orchestrator.

## 2. What it adds to the project
- A new package `src/strategy/` (the brain tier — client-side, never in an MCP server):
  - `evaluate.py` — a tunable heuristic state-evaluation function (features below).
  - `minimax.py` — `MinimaxMover` (alpha-beta over the real 8-dir game tree; depth & weights from config; **considers `PLACE_BARRIER` as a legal candidate**).
  - `qtable.py` — `QTableMover` (loads a trained table, plays greedy/argmax at runtime).
  - `train.py` — offline self-play **trainer** that writes a Q-table JSON (run once; the table is committed so runtime never needs to train).
  - `factory.py` — `build_mover(role, config)` mapping a config name (`minimax|qtable|greedy|random`) to a `Mover` instance.
- A `models/` directory holding the committed trained Q-table JSON.
- A new `strategy:` block in `config.yaml` (brain selection per role + minimax/qtable knobs).
- `tests/test_strategy/` proving brain selection, minimax strength vs greedy, search purity (no board mutation leak), Q-table load/play, and resizability across the sanity ladder.

## 3. Scope
**In scope:**
- `MinimaxMover` for **both roles** (Cop maximizes capture, Thief maximizes survival — one zero-sum evaluation; Cop is MAX, Thief is MIN).
- A tunable heuristic `evaluate(state, config)` used at search leaves.
- `QTableMover` + offline `train.py` (optional per §8, but built now per Director's call).
- Keep `GreedyMover` (Step 3) as a selectable baseline/fallback.
- Config-driven brain selection per role; all knobs (depth, weights, qtable path/params) in `config.yaml`.
- Barriers remain a **legal candidate** the search may pick (it rarely will — see §4 findings); no change to the barrier rule.
- Resizability proven across 2×2…5×5; no hard-coded grid/params in `src/strategy/`.
- Determinism/reproducibility preserved (fixed tie-break; runtime argmax; seeded training).

**Out of scope (deferred):**
- Natural-language messaging / location inference / deception → **Step 5**. The brain reads the **full** `GameState` now; Step 5 swaps in the per-agent partial observation (the Step-3 `observe()` seam).
- Any change to movement or barrier rules (8-dir + own-cell barrier are **assignment-mandated**, §4.2/§4.3).
- Tuning for a bigger competition board / using the §4.2 "strategic start position" lever → not pursued (Director chose the **official 5×5**).
- Deep RL / neural nets (§8 explicitly limits to **tabular** Q-learning, optional).
- GUI (Step 6), cloud (Step 7), Gmail report (Step 8).

## 4. Chosen approach (and what we rejected)
**Decision:** A **config-selectable `Mover` family** behind the existing seam:
`MinimaxMover` (primary) + `QTableMover` (optional) + `GreedyMover` (baseline). Minimax
uses **alpha-beta** over the real game tree with a **tunable containment heuristic** at
leaves; both roles share one zero-sum evaluation. Movement and barriers are unchanged.

**Why:** The assignment is explicit that **the strategy algorithm is not what earns the
grade** (§2, §3) — orchestration/communication is — so the brain must be *correct,
swappable, and config-driven* rather than maximally clever. Minimax is the strongest
brain we can ship today for the **separate bonus competition** and dominates greedy on
non-trivial boards (see findings). Keeping everything behind the one `Mover` seam means
the orchestrator (Step 3) and the servers (Step 2) need **zero** changes, and Step 5 can
later wrap these movers with partial-observation NL inference at the same seam.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Minimax + Q-Table + keep Greedy, config-selectable | ✅ chosen | Strong for the bonus; ships today; satisfies §8's optional Q-Table; one clean seam |
| Greedy only (strategy isn't graded) | ❌ rejected by Director | Adequate for the grade but weakest in the bonus competition |
| **Switch to 4-directional movement** to make barriers useful | ❌ **rejected — violates §4.2** | §4.2 mandates "movement in all directions, including diagonally"; would also break interop with other groups |
| Change the barrier rule (ranged / free walls) to make barriers matter | ❌ rejected — violates §4.3 | §4.3 fixes barriers to the Cop's own cell, costing the turn |
| Deep RL / neural Q-network | ❌ rejected | §8 limits to **tabular** Q-learning and marks even that optional |
| Minimax considers `PLACE_BARRIER` as a candidate | ✅ chosen | Honest: the search *may* wall when beneficial; it legally can, even if it rarely does |

**Empirical findings that justify this (from playtesting the real engine — fold into the README):**
- On the **default 5×5, the game is a forced Cop win**: even pure greedy Cop beats every Thief 100% in ~7 plies and **never needs a barrier**. King moves make the grid "cop-win" (dismantlable; classic *cops & robbers* theory — the grid's cop-number is 2 for orthogonal moves, but 8-dir king moves are cop-win for a single cop), the Thief moves first and cannot pass, and 25 plies is ample.
- **Consequence:** on 5×5 the bonus competition **ties 75–75 for everyone** (each group: Cop 20×3 + Thief 5×3 = 75), because skill cannot change a forced outcome. Skill only differentiates on **bigger boards** — where `MinimaxMover` Cop wins **100%** vs a greedy Thief while a **greedy Cop wins only ~20%** (9×9, 25 moves). This is the bonus edge if a larger board is ever used.
- **Barriers are strategically inert for the Cop under the mandated 8-dir rule** — tested own-cell (current), adjacent, and even *free* walls against an optimal Thief: the optimal Cop places **0** barriers (a single wall blocks at most 1 of a king's 8 escape directions, and walling costs a tempo). Barriers would only matter under orthogonal movement, which §4.2 forbids. We therefore keep barriers correct and legal, let the search consider them, and **document the analysis** rather than chase a non-existent barrier strategy.

## 5. Dependencies & interfaces
- **Consumes from prior steps:**
  - `src/game/movers.py`: the `Mover` protocol (`choose_move(state) -> Move`) and `GreedyMover`/`RandomMover`.
  - `src/game/`: `legal_moves`, `apply_move`, `Move`, `GameState`, `initial_state`, and rules `is_capture`/`is_timeout`/`score_sub_game`; `Board` (for cloning).
  - `src/game/config.py`: the `Config` loader (extend with the `strategy:` block).
- **Exposes to later steps:**
  - `build_mover(role, config) -> Mover` — the factory the orchestrator/CLI uses to pick brains. The orchestrator's `run_series(config, gateways, group_a, group_b)` and `engine.play_series`/`play_sub_game` already accept `Mover` objects, so they consume these unchanged.
  - The `Mover` instances are the exact objects **Step 5** will wrap to feed NL-derived partial observations instead of full `GameState`.
- **Touches config keys:** adds a new top-level `strategy:` block (see §7). No change to existing game/server/output keys.

## 6. Binding constraints (from the assignment)
- **Movement is 8-directional incl. diagonals (§4.2)** — do **not** alter; distance metric is therefore **Chebyshev** (king-move minimum steps).
- **Barriers per §4.3** — Cop-only, own cell, costs the turn, impassable to both, max 5; unchanged.
- **Brain lives in the client tier** — `src/strategy/` is client-side; MCP servers stay validate-only and untouched (server/client split, §5/§5.2).
- **No hard-coding / resizable (§4.2, §4.5)** — grid size, depth, weights, qtable params all from `config.yaml`; prove on the 2×2…5×5 ladder. No literal `5`/`25`/etc. game values in `src/strategy/`.
- **Free-NL future-proofing** — the `Mover` seam shape is fixed; Step 5 must be able to drop in partial-observation brains without changing the protocol.
- **Q-Learning is tabular and optional (§8)** — no deep nets.

## 7. Key design decisions
- **Files/modules to create:**
  - `src/strategy/__init__.py`
  - `src/strategy/evaluate.py` — `evaluate(state, config) -> float` (Cop's perspective; + = good for Cop). Features: `-w_dist*chebyshev(cop,thief)`, `-w_thief_mob*thief_open_neighbours`, `+w_corner*thief_corner_pressure`, `-w_reach*thief_reachable_area(within remaining-budget, BFS, walls block)`. Terminal shortcuts: capture → `+CAP - moves_used` (prefer faster), timeout → `-CAP + moves_used`. Weights from `config.strategy.minimax.weights`.
  - `src/strategy/minimax.py` — `MinimaxMover(depth, weights)`: alpha-beta; Cop is MAX, Thief is MIN; candidates = `legal_moves(state)` (**includes `PLACE_BARRIER`**); **clones state per node** (see gotcha); deterministic tie-break (keep first best in `Move` declaration order). Returns the chosen `Move`.
  - `src/strategy/qtable.py` — `QTableMover(table_path)`: loads JSON; at runtime picks `argmax_a Q(abstract_state, a)` over legal moves with deterministic tie-break; falls back to greedy/first-legal on unseen states.
  - `src/strategy/train.py` — offline tabular Q-learning via self-play (`python -m src.strategy.train`): ε-greedy exploration (seeded), reward per §8 (small step/“fuel” penalty, capture reward for Cop / survival reward for Thief), **random start positions** (§4.2) so the table generalizes across the board; writes `models/qtable.json`.
  - `src/strategy/factory.py` — `build_mover(role, config) -> Mover`: `"minimax"`→`MinimaxMover`, `"qtable"`→`QTableMover`, `"greedy"`→`GreedyMover`, `"random"`→`RandomMover`.
  - `models/qtable.json` — committed trained table (so a fresh checkout runs without training).
  - `tests/test_strategy/` — see acceptance.
- **Core data structures:**
  - Reuse `GameState`, `Move`, `Board`.
  - **State clone helper** (in `minimax.py` or a small util): deep-copies `GameState` *and* a fresh `Board` with a copied `barriers` set — required because `apply_move` **mutates** the shared `Board` on `PLACE_BARRIER`.
  - **Q-table key (abstraction):** a compact, board-size-agnostic tuple, e.g. `(clamped Δrow, clamped Δcol between self and opponent, to_move, barriers_left_bucket)`; value = dict `{move_name: q}`. Keep abstraction documented in `qtable.py`.
- **Key signatures (intent):**
  - `evaluate(state, config) -> float`
  - `class MinimaxMover: __init__(self, depth, weights); choose_move(self, state) -> Move`
  - `class QTableMover: __init__(self, table_path); choose_move(self, state) -> Move`
  - `build_mover(role: str, config) -> Mover`
  - `train(config, out_path) -> None`
- **Distance metric:** Chebyshev (8-dir). **Determinism:** minimax fixed tie-break (no RNG) → reproducible like Step 3; Q-table argmax deterministic at runtime; randomness only in `train.py` (seeded).
- **Config-agnostic brains:** every brain takes only `config` + `state`; nothing about board size is baked in.

## 8. Acceptance criteria (how we know the step is done)
1. `config.strategy.cop` / `config.strategy.thief` select the brain per role; the default config runs a full `num_games` series end-to-end on 5×5 (via `engine.play_series` and via the Step-3 orchestrator) with the selected brains, scores in the §4.4 band.
2. `build_mover` returns the right `Mover` type for each of `minimax|qtable|greedy|random`; unknown names raise a clear error.
3. **Minimax ≥ greedy:** on a non-trivial board (e.g. 9×9, 25 moves) a `MinimaxMover` Cop captures a greedy Thief in cases where a `GreedyMover` Cop times out — a test asserts minimax's capture rate ≥ greedy's (strictly greater on at least one seeded start).
4. **Search purity:** running `MinimaxMover.choose_move` does **not** mutate the caller's `GameState`/`Board` (a test snapshots `state.board.barriers` before/after and asserts equality) — proves per-node cloning.
5. **Barrier is considered:** a test confirms `PLACE_BARRIER` is among the candidates the Cop's search evaluates when `cop_barriers_left > 0` (even if not chosen).
6. **Q-Table:** `train.py` produces `models/qtable.json`; a `QTableMover` loads it and plays a full **legal** series (every chosen move ∈ `legal_moves`); argmax is deterministic across two runs.
7. **Resizable / no hard-coding:** all brains run on 2×2, 3×3, 4×4, 5×5 from config; grepping `src/strategy/` finds no literal game numbers; depth/weights/qtable params come from `config`.
8. `pytest -q` passes (existing 63 + new strategy tests).

## 9. Resolved questions / open items
- **Q:** Make barriers useful by switching to 4-dir movement? → **A:** **No — §4.2 mandates 8-dir incl. diagonals.** Barriers stay as locked; the search may use them but won't often. Documented as a finding, not a failing.
- **Q:** Which brain(s)? → **A:** **Minimax (primary) + Q-Table (optional, §8) + keep Greedy** (baseline), all config-selectable. (Director chose to build all now.)
- **Q:** Competition board? → **A:** **Follow the official 5×5.** (Note for the record: 5×5 is a forced Cop win ⇒ the bonus ties 75–75 for all; the minimax edge only shows on bigger boards. Not pursued now.)
- **Q:** Is Q-Table required? → **A:** No (§8 optional/recommended) — but built this step per Director's call; runtime uses a **committed** trained table.
- **Q:** Start positions? → **A:** Keep the locked fixed corners for the official run (deterministic). `train.py` uses **random** starts internally so the Q-table generalizes (§4.2 permits random/strategic starts).
- **Q:** Distance metric? → **A:** **Chebyshev** (8-dir king moves).
- **Still open (note for Builder):** none — all rules sourced from the PDF (§2–§4, §8).

## 10. Notes for the Builder session
- **Put the most TODO detail in `minimax.py` and `evaluate.py`** — give the alpha-beta loop and the eval feature set as copy-paste code with exact signatures. The brain is the substance of this step.
- **CRITICAL gotcha — clone before searching.** `apply_move(state, PLACE_BARRIER)` calls `board.place_barrier(state.cop_pos)`, which **mutates the shared `Board`** (the returned `GameState` reuses the same `board` reference). The minimax expansion **must** clone `GameState` *and* a fresh `Board` (copy `rows`, `cols`, and `set(barriers)`) for every child, or the search will corrupt the live game and sibling branches. Acceptance #4 tests exactly this.
- **Reuse the engine, don't re-implement rules.** Candidates come from `legal_moves(state)`; expansion uses `apply_move` on the **clone**; terminals use `is_capture`/`is_timeout`. The only new logic is search + evaluation.
- **`MinimaxMover` is one class for both roles** — Cop is MAX, Thief is MIN, branch on `state.to_move`. Use a fixed `Move` ordering for deterministic tie-breaks (mirror `GreedyMover`'s reproducibility).
- **Keep depth small** (config default ~3–4) so a series runs fast; alpha-beta + a 9-wide branching factor is fine at that depth.
- **Distance is Chebyshev** (not Manhattan) — moves are 8-directional.
- **Config:** add a `strategy:` block with trailing-optional fields so existing positional `Config` construction stays valid (same pattern Steps 2/3 used for `servers`/`output`). Suggested shape:
  ```yaml
  strategy:
    cop: minimax        # minimax | qtable | greedy | random
    thief: minimax
    minimax:
      depth: 4
      weights: { dist: 1.0, thief_mob: 0.3, corner: 0.2, reach: 0.15, capture: 1000.0 }
    qtable:
      path: "models/qtable.json"
      train: { episodes: 20000, alpha: 0.3, gamma: 0.95, epsilon: 0.2, seed: 7 }
  ```
- **Commit the trained Q-table** (`models/qtable.json`) so a fresh checkout runs `qtable` without training; `train.py` is the reproducer, not a runtime dependency. Add `models/` to the repo (do **not** gitignore the table).
- **Q-table abstraction:** key on **relative** opponent offset (clamped) + `to_move` + barriers-left bucket so one table works across grid sizes; on unseen keys fall back to greedy/first-legal. Don't over-engineer — it's optional per §8.
- **Tests across the sanity ladder** (2×2…5×5), and a no-stray-literals grep over `src/strategy/`.
- **Document the barrier / cop-number finding** (§4 here) in the PRD and flag it for the README — it is a genuine, honest insight that will stand out to the grader.
