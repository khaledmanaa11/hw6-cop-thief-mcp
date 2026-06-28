# PRD — Step 4: Decision Engine (strategy brain)

| Field | Value |
|-------|-------|
| Component | `step4_decision_engine` (strategy / brain tier) | Version | 1.00 | Depends on | Step 1 (`src/game/`), Step 3 (`src/orchestrator/`, `Mover` seam) |

- **Status:** triplet-built — awaiting Director approval (§2.5) before any code
- **Source:** `DECISION_step4_decision_engine.md`
- **Cross-links:** `PLAN_step4_decision_engine.md` (architecture) · `TODO_step4_decision_engine.md` (atomic build order)
- **Assignment references:** §2 (strategy is *recommendation only*, not graded); §3 (central metric = orchestration/communication, **not** the game-strategy algorithm; bonus competition ≤10 pts is separate); §4.1 (sub-game ≤25 plies, Thief first); §4.2 (**8-directional movement incl. diagonals — mandatory**; board resizable; starts may be random/strategic); §4.3 (barriers: Cop walls its own current cell, costs the turn, impassable, max 5, Thief none); §4.4 (Table 1 scoring); §4.5 (sanity ladder 2×2→5×5); §8 (Tabular Q-Learning **optional, recommended only** — built this step per Director's call).

## 1. Description & theoretical background (§2.3)
Step 3 wired a full distributed run but drove both agents with a placeholder `GreedyMover`
(pure Chebyshev pursue/evade). Step 4 is the **brain step**: it replaces that placeholder with a
**real, config-selectable decision engine** behind the *unchanged* `Mover` seam
(`choose_move(state) -> Move`). It adds a depth-limited **minimax / alpha-beta** strategist (the
primary brain, for the separate bonus competition) and an **optional Tabular Q-Learning** strategist
(per §8), while keeping `GreedyMover` as a baseline/fallback. Which brain drives the Cop and which
drives the Thief is chosen entirely from `config.yaml`. Theoretically this turns the agents from
reactive 1-ply hill-climbers into **adversarial lookahead** players: minimax treats the sub-game as
the zero-sum pursuit game it is (Cop is MAX, Thief is MIN over one shared evaluation), and tabular
Q-learning approximates the same value function from self-play. Crucially, the assignment says the
strategy algorithm is **not what earns the grade** — so the brain must be *correct, swappable, and
config-driven* rather than maximally clever. Movement stays 8-directional and barriers stay exactly as
locked; the search merely *considers* them. After this step the project has agents that pursue and
evade with genuine lookahead and can be swapped/tuned without touching the engine, servers, or
orchestrator — and Step 5 can wrap these same movers with partial-observation NL inference at the
same seam.

## 2. Inputs / Outputs / performance metrics (§2.3)
- **Input:** `config.yaml` — all existing Step-1/2/3 keys **plus** a new top-level `strategy:` block
  (`strategy.cop`, `strategy.thief` ∈ `minimax|qtable|greedy|random`; minimax `depth`/`weights`;
  qtable `path`/training params). For `qtable`, a committed trained table at `models/qtable.json`.
  Each brain receives only `(config, GameState)` — nothing about board size is baked in.
- **Output:** a `Mover` instance per role from `build_mover(role, config)`, plugged straight into the
  Step-3 orchestrator / `engine.play_series`; `train.py` additionally produces the committed
  `models/qtable.json`. No change to the transcript / replay / telemetry output shapes — Step 4 only
  changes *which moves get chosen*, not how a run is recorded.
- **Performance:** correctness and swappability over raw strength (strategy isn't graded). Minimax at
  the config-default depth (~3–4) with alpha-beta over a ≤9-wide branching factor runs a full 6-sub-game
  5×5 series in well under a minute locally. Determinism is a hard metric: minimax uses a fixed
  tie-break (no RNG) and the Q-table plays deterministic argmax at runtime, so replays stay
  reproducible exactly as in Step 3. Training (`train.py`) is offline/seeded and run **once** — never a
  runtime dependency.

## 3. Functional requirements
- **FR-S1 — `src/strategy/` brain package.** A new client-side package (never inside an MCP server)
  holding every brain and the factory. Importable as `src.strategy`.
- **FR-S2 — `evaluate(state, config) -> float`.** A tunable heuristic state-evaluation from the **Cop's
  perspective** (+ = good for Cop): `-w_dist*chebyshev(cop,thief)`, `-w_thief_mob*thief_open_neighbours`,
  `+w_corner*thief_corner_pressure`, `-w_reach*thief_reachable_area` (BFS within remaining budget, walls
  block). Terminal shortcuts: capture → `+CAP - moves_used` (prefer faster), timeout →
  `-CAP + moves_used`. All weights from `config.strategy.minimax.weights`; **no literal game numbers**.
- **FR-S3 — `MinimaxMover` (alpha-beta, both roles).** One class: Cop is MAX, Thief is MIN, branch on
  `state.to_move`. Candidates = `legal_moves(state)` (**includes `PLACE_BARRIER`** when
  `cop_barriers_left > 0`). Depth and weights from config. Leaf value = `evaluate(...)`; terminals use
  `is_capture`/`is_timeout`. Returns a `Move`; deterministic tie-break (first best in `Move` declaration
  order, no RNG).
- **FR-S4 — Search purity (clone before expanding).** `MinimaxMover.choose_move` must **not** mutate the
  caller's `GameState`/`Board`. Because `apply_move(state, PLACE_BARRIER)` mutates the shared `Board`,
  every search child clones `GameState` *and* a fresh `Board` (copy `rows`, `cols`, `set(barriers)`).
- **FR-S5 — `QTableMover` (optional, §8).** Loads `models/qtable.json`; at runtime picks
  `argmax_a Q(abstract_state, a)` over legal moves with deterministic tie-break; falls back to
  greedy/first-legal on unseen states. Every chosen move is always ∈ `legal_moves`.
- **FR-S6 — `train.py` offline trainer.** `python -m src.strategy.train` runs seeded ε-greedy
  self-play with **random start positions** (§4.2), rewards per §8 (step/fuel penalty + capture reward
  for Cop / survival reward for Thief), and writes `models/qtable.json`. Run once; the table is
  committed so a fresh checkout never trains.
- **FR-S7 — `build_mover(role, config) -> Mover` factory.** Maps a config name
  (`minimax|qtable|greedy|random`) to the right `Mover`; unknown names raise a clear error. This is the
  single entry point the orchestrator/CLI uses to pick brains.
- **FR-S8 — Barriers unchanged, merely considered.** No change to the §4.3 barrier rule; the search may
  legally pick `PLACE_BARRIER` but (per the empirical finding) rarely will. Documented, not forced.
- **FR-S9 — Config-driven / resizable.** Brain selection per role and all knobs (depth, weights, qtable
  path/params) come from `config.yaml`; brains run across the 2×2…5×5 ladder; no literal game numbers in
  `src/strategy/`.
- **FR-S10 — Determinism preserved.** Minimax fixed tie-break, Q-table runtime argmax deterministic;
  randomness exists **only** inside seeded `train.py`. Replays stay reproducible like Step 3.
- **FR-S11 — Seam unchanged for Step 5.** The `Mover` protocol shape is fixed; these movers are the
  exact objects Step 5 will wrap to feed NL-derived partial observations instead of full `GameState`.

## 4. Constraints, limitations, alternatives considered (§2.3)
- **8-directional movement (§4.2):** mandatory — distance metric is therefore **Chebyshev** (king-move
  minimum steps). · Alternative rejected: **switch to 4-directional** to make barriers strategically
  useful — **violates §4.2** ("movement in all directions, including diagonally") and breaks interop
  with other groups.
- **Barriers per §4.3 unchanged:** Cop-only, own cell, costs the turn, impassable, max 5. · Alternative
  rejected: ranged / free / adjacent walls to make barriers matter — **violates §4.3**; and empirically
  an optimal Cop places **0** barriers even with free walls under 8-dir movement (a single wall blocks
  ≤1 of a king's 8 escape directions and walling costs a tempo).
- **Brain lives in the client tier:** `src/strategy/` is client-side; MCP servers stay validate-only and
  untouched (§5/§5.2). · Alternative rejected: search logic in a server — breaks the Step-2 stateless
  lock.
- **Minimax (primary) + Q-Table (optional) + keep Greedy (baseline), all config-selectable** (Director's
  call to build all now). · Alternatives rejected: greedy-only (adequate for the grade, weakest in the
  bonus); deep RL / neural Q-network (**§8 limits to tabular**, even that optional).
- **Empirical limitation (honest finding, fold into README):** on the **default 5×5 the game is a
  forced Cop win** — even a greedy Cop beats every Thief 100% in ~7 plies and never needs a barrier
  (8-dir king moves make the grid cop-win for one cop; Thief moves first and can't pass; 25 plies is
  ample). **Consequence:** the bonus competition **ties 75–75 for everyone** on 5×5 (Cop 20×3 + Thief
  5×3), because skill can't change a forced outcome. The minimax edge only appears on **bigger boards**
  (e.g. 9×9, 25 moves: minimax Cop wins 100% vs a greedy Thief while a greedy Cop wins ~20%). We keep
  barriers correct, let the search consider them, and **document** the analysis rather than chase a
  non-existent barrier strategy.
- **Config:** one new top-level `strategy:` block with trailing-optional fields, so existing positional
  `Config(...)` construction stays valid (same backward-compatible pattern Steps 2/3 used for
  `servers`/`output`).

## 5. Success criteria & test scenarios (§2.3)
- **R-AC1** — Brain selection end-to-end: `config.strategy.cop`/`thief` pick the brain per role; the
  default config runs a full `num_games` series on 5×5 (via `engine.play_series` **and** via the Step-3
  orchestrator) with the selected brains and scores in the §4.4 `[30, 90]` band. → *test:*
  `test_series_with_minimax_band`.
- **R-AC2** — Factory: `build_mover` returns the right `Mover` type for each of
  `minimax|qtable|greedy|random`; an unknown name raises a clear error. → *test:*
  `test_build_mover_types`, `test_build_mover_unknown_raises`.
- **R-AC3** — **Minimax ≥ greedy:** on a non-trivial board (9×9, 25 moves) a `MinimaxMover` Cop captures
  a greedy Thief where a `GreedyMover` Cop times out; assert minimax capture rate ≥ greedy's, strictly
  greater on ≥1 seeded start. → *test:* `test_minimax_beats_greedy_9x9`.
- **R-AC4** — **Search purity:** `MinimaxMover.choose_move` does not mutate the caller's
  `GameState`/`Board` (snapshot `state.board.barriers` + positions before/after, assert equality) —
  proves per-node cloning. → *test:* `test_minimax_search_is_pure`.
- **R-AC5** — **Barrier considered:** when `cop_barriers_left > 0`, `PLACE_BARRIER` is among the
  candidates the Cop's search evaluates (even if not chosen). → *test:* `test_barrier_is_candidate`.
- **R-AC6** — **Q-Table:** `train.py` produces `models/qtable.json`; a `QTableMover` loads it and plays
  a full series where every chosen move ∈ `legal_moves`; argmax is identical across two runs. → *test:*
  `test_qtable_loads_and_plays`, `test_qtable_argmax_deterministic`.
- **R-AC7** — **Resizable / no hard-coding:** all brains run on 2×2, 3×3, 4×4, 5×5 from config; grep of
  `src/strategy/` finds no literal game numbers; depth/weights/qtable params come from `config`. → *test:*
  `test_brains_resizable_ladder` + grep check.
- **R-AC8** — Full suite green: `pytest -q` passes (existing 63 + new strategy tests). → *test:*
  `pytest -q`.

## Non-goals
- Natural-language messaging / location inference / deception → **Step 5** (the brain reads the **full**
  `GameState` now; Step 5 swaps in the per-agent partial observation at the Step-3 `observe()` seam).
- Any change to movement or barrier rules — both are assignment-mandated (§4.2/§4.3).
- Tuning for a bigger competition board / using the §4.2 "strategic start" lever — not pursued (Director
  chose the **official 5×5**; the edge only shows on larger boards, noted for the record).
- Deep RL / neural nets — §8 limits to **tabular** Q-learning.
- GUI (Step 6), cloud deploy (Step 7), Gmail report (Step 8).
