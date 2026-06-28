# TODO — Step 4: Decision Engine (strategy brain)

> Implements `PRD_step4_decision_engine.md` + `PLAN_step4_decision_engine.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**
> One step = one commit = one `/relay-next`. When ready to build, copy these into `docs/PROGRESS.md`.

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never hard-code** game parameters — no literal `5` / `25` / `8` / board coords in `src/strategy/`. Read grid bounds from `state.board.rows/cols`; read depth/weights/qtable params from `config.strategy`.
4. Do not assume a 5×5 grid; bounds always come from the state/config. Prove brains on the 2×2…5×5 ladder.
5. If a box seems ambiguous, STOP and ask — do not guess.
6. **Reuse the Step-1 engine** (`legal_moves`, `apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`, `SubGameResult`/`SeriesResult`). The only new logic is **search + evaluation + Q-table I/O**. Do not re-implement a rule.
7. **The brain lives in the client tier.** Do NOT touch `src/mcp_servers/` or `src/orchestrator/`; the `Mover` seam is unchanged.
8. **Search must be pure** — clone `GameState` *and* a fresh `Board` before expanding any child (see B-phase gotcha). Never mutate the caller's state.
9. Run every command from the repository root (the folder containing `config.yaml`).

## Conventions
- Language/runtime: **Python 3.12**. Source root: `src/` · Tests: `tests/`.
- Each box format: **ID · file · action · detail · Check.**
- **Distance metric is Chebyshev** `max(|dr|, |dc|)` (moves are 8-directional king moves) — never Manhattan.
- **`MinimaxMover` is ONE class for both roles:** Cop is MAX, Thief is MIN, branch on `state.to_move`. Deterministic tie-break = keep the first best in `Move` declaration order (no RNG), mirroring `GreedyMover`.
- **Move names** are `Move` enum members (`src/game/moves.py`): `N S E W NE NW SE SW PLACE_BARRIER`. Minimax includes `PLACE_BARRIER` among candidates when `cop_barriers_left > 0`; greedy/qtable need not.
- **`evaluate` is Cop-perspective:** `+` = good for Cop, `-` = good for Thief. Weights come from `config.strategy.minimax.weights`.
- **Commit `models/qtable.json`** — do NOT gitignore it. `train.py` is the reproducer, not a runtime dependency.

---

## Phase A — config & factory groundwork

- [ ] **A1** — `src/game/config.py` — edit — add an optional trailing `strategy` field to `Config` (a dict or small dataclass) and parse a top-level `strategy:` block in `load_config` **if present**, else default to `{"cop": "minimax", "thief": "minimax", "minimax": {...}, "qtable": {...}}`. Field must be **last** so existing positional `Config(...)` construction stays valid (same pattern as `servers`/`output`).
      **Check:** `python -c "from src.game.config import load_config; c=load_config('config.yaml'); print(c.strategy['cop'], c.strategy['thief'])"` prints `minimax minimax`; existing `tests/test_game/test_config.py` still passes.

- [ ] **A2** — `config.yaml` — edit — append the `strategy:` block from PLAN §3 (cop/thief selectors + `minimax.depth`/`minimax.weights` + `qtable.path`/`qtable.train`). Keep all existing keys unchanged.
      **Check:** `python -c "import yaml; d=yaml.safe_load(open('config.yaml'))['strategy']; print(d['cop'], d['minimax']['depth'], d['qtable']['path'])"` prints `minimax 4 models/qtable.json`.

- [ ] **A3** — `src/strategy/__init__.py` — new — empty file to make `src.strategy` an importable package.
      **Check:** `python -c "import src.strategy; print('ok')"` prints `ok`.

- [ ] **A4** — `src/strategy/factory.py` — new — `build_mover(role: str, config) -> Mover` mapping the per-role name (`config.strategy[role]`) to a `Mover`: `"greedy"`→`GreedyMover`, `"random"`→`RandomMover`, `"minimax"`→`MinimaxMover(depth, weights)`, `"qtable"`→`QTableMover(path)`. Unknown name → `ValueError` with a clear message. (Import minimax/qtable lazily so A4 lands before B/C.)
      **Check:** `test_build_mover_types` — `build_mover("cop", config)` returns the type named by `config.strategy["cop"]` for greedy/random; `test_build_mover_unknown_raises` — an unknown name raises `ValueError`. Satisfies R-AC2.

## Phase B — minimax brain (the substance)

- [ ] **B1** — `src/strategy/evaluate.py` — new — `evaluate(state, config) -> float` (Cop-perspective, FR-S2): terminal shortcuts first — `is_capture(state)` → `+w_capture - moves_used`, `is_timeout(state)` → `-w_capture + moves_used`; otherwise `-w_dist*chebyshev(cop,thief) - w_thief_mob*thief_open_neighbours + w_corner*thief_corner_pressure - w_reach*thief_reachable_area` (BFS within remaining ply budget, walls block). Pull all weights from `config.strategy.minimax.weights`; grid bounds from `state.board`. No literal game numbers.
      **Check:** `test_evaluate_prefers_capture` — a captured state scores higher than any non-terminal; a state with the Cop adjacent to the Thief scores higher than one far away (same board). `pytest -q` green.

- [ ] **B2** — `src/strategy/minimax.py` — new — add the **clone helper** `_clone(state) -> GameState` that deep-copies `GameState` **and** a fresh `Board` (copy `rows`, `cols`, `set(barriers)`). **GOTCHA:** `apply_move(state, PLACE_BARRIER)` mutates the shared `Board`; expansion MUST happen on a clone (FR-S4 / R-AC4).
      **Check:** `test_clone_is_independent` — mutating a clone's `board.barriers` does not change the original's.

- [ ] **B3** — `src/strategy/minimax.py` — edit — add `class MinimaxMover` with `__init__(self, depth, weights)` and `choose_move(self, state) -> Move` (FR-S3): alpha-beta over `legal_moves(state)` (**include `PLACE_BARRIER`**); Cop=MAX, Thief=MIN by `state.to_move`; expand each candidate on `_clone` via `apply_move`; recurse to `depth` or terminal; leaf value = `evaluate(node, config-equivalent weights)`; return the top-level `Move` with the best value, **first best in `Move` enum order** on ties (no RNG).
      **Check:** `test_minimax_search_is_pure` — snapshot `state.cop_pos/thief_pos/board.barriers` before and after `choose_move`; assert unchanged (R-AC4). `test_barrier_is_candidate` — with `cop_barriers_left > 0`, instrument/inspect that `PLACE_BARRIER` is among the Cop's evaluated candidates (R-AC5).

- [ ] **B4** — `tests/test_strategy/test_minimax.py` — new — `test_minimax_beats_greedy_9x9` (FR-S3 / R-AC3): on a 9×9, 25-move config, run a `MinimaxMover` Cop vs a `GreedyMover` Thief and a `GreedyMover` Cop vs the same Thief across several seeded starts; assert minimax capture rate ≥ greedy's and **strictly greater on ≥1 start**.
      **Check:** `pytest -q tests/test_strategy/test_minimax.py` green.

## Phase C — Q-Learning brain (optional per §8, built now)

- [ ] **C1** — `src/strategy/qtable.py` — new — `class QTableMover` with `__init__(self, table_path)` (load JSON once) and `choose_move(self, state) -> Move` (FR-S5): compute the **board-size-agnostic** abstract key `(clamped Δrow, clamped Δcol, to_move, barriers_left_bucket)`; pick `argmax_a Q(key, a)` over `legal_moves(state)` with deterministic tie-break; on an unseen key fall back to greedy/first-legal. Document the abstraction in a docstring.
      **Check:** `test_qtable_loads_and_plays` — with a small hand-written table JSON, every chosen move over a 3×3 series is ∈ `legal_moves`; `test_qtable_argmax_deterministic` — two runs from the same state return the identical move (R-AC6).

- [ ] **C2** — `src/strategy/train.py` — new — `train(config, out_path)` + `python -m src.strategy.train` (FR-S6): seeded ε-greedy self-play with **random start positions** (§4.2); reward per §8 (step/fuel penalty + capture reward for Cop / survival reward for Thief); update Q via the configured `alpha`/`gamma`/`epsilon`/`episodes`/`seed`; write `out_path` (default `config.strategy.qtable.path`) as JSON. Runtime never imports this module.
      **Check:** `python -m src.strategy.train` writes `models/qtable.json` (non-empty, valid JSON); rerun with the same seed produces an identical file (determinism).

- [ ] **C3** — `models/qtable.json` — new (generated by C2) — commit the trained table so a fresh checkout runs `qtable` without training. Ensure `models/` is **not** gitignored.
      **Check:** `git check-ignore models/qtable.json` prints nothing (i.e. it IS tracked); `python -c "import json; json.load(open('models/qtable.json'))"` succeeds.

## Phase D — integration & resizability

- [ ] **D1** — `tests/test_strategy/test_factory.py` — new — round out `build_mover` coverage: assert `minimax`/`qtable` names return `MinimaxMover`/`QTableMover` built from `config.strategy` knobs (depth/weights/path threaded through). Satisfies R-AC2.
      **Check:** `pytest -q tests/test_strategy/test_factory.py` green.

- [ ] **D2** — `tests/test_strategy/test_series.py` — new — `test_series_with_minimax_band` (FR-S1 / R-AC1): build movers via `build_mover` from the default config and run a full `num_games` series on 5×5 through `engine.play_series`; assert group totals in `[30, 90]`. (Engine-only; no servers/sockets.)
      **Check:** `pytest -q tests/test_strategy/test_series.py` green.

- [ ] **D3** — `tests/test_strategy/test_resizable.py` — new — `test_brains_resizable_ladder` (FR-S9 / R-AC7): for each of `minimax`, `qtable`, `greedy`, run a short series on 2×2, 3×3, 4×4, 5×5 (config overrides); assert each completes and returns engine-parity scores with only legal moves.
      **Check:** `pytest -q tests/test_strategy/test_resizable.py` green; no real sockets opened.

- [ ] **D4** — repo root — verify — grep gate: no literal game numbers / board constants in `src/strategy/`, and the full suite passes.
      **Check:** `grep -rnE "\b(5|25|8)\b" src/strategy/` returns nothing that is a game value (weights/keys excepted — review by eye); `pytest -q` green (existing 63 + new strategy tests) — satisfies R-AC7 / R-AC8.

---

## Coverage matrix (§6 — every requirement has a test)
| Requirement | Step(s) | Test |
|-------------|---------|------|
| FR-S1 (`src/strategy/` package) | A3, D2 | `tests/test_strategy/test_series.py::test_series_with_minimax_band` (R-AC1) |
| FR-S2 (`evaluate`) | B1 | `tests/test_strategy/test_evaluate.py::test_evaluate_prefers_capture` |
| FR-S3 (`MinimaxMover` α-β) | B2, B3, B4 | `tests/test_strategy/test_minimax.py::test_minimax_beats_greedy_9x9` (R-AC3) |
| FR-S4 (search purity / clone) | B2, B3 | `test_minimax.py::test_minimax_search_is_pure` (R-AC4) |
| FR-S5 (`QTableMover`) | C1 | `test_strategy/test_qtable.py::test_qtable_loads_and_plays` (R-AC6) |
| FR-S6 (`train.py`) | C2, C3 | `python -m src.strategy.train` writes/commits `models/qtable.json` |
| FR-S7 (`build_mover` factory) | A4, D1 | `test_strategy/test_factory.py::test_build_mover_types` (R-AC2) |
| FR-S8 (barrier considered) | B3 | `test_minimax.py::test_barrier_is_candidate` (R-AC5) |
| FR-S9 (config-driven/resizable) | A1–A2, D3, D4 | `test_strategy/test_resizable.py` + grep (R-AC7) |
| FR-S10 (determinism) | B3, C1, C2 | `test_qtable.py::test_qtable_argmax_deterministic` + seeded train rerun |
| FR-S11 (seam unchanged for Step 5) | A4, D2 | series runs through `engine.play_series` with no orchestrator/server change |

## `{TBD}` — for Director sign-off (§2.5)
1. **Minimax default depth** — `4` proposed in `config.yaml`. Confirm it keeps a full 6-sub-game 5×5 series fast on the target machine; lower to `3` if a series is sluggish.
2. **Q-table abstraction granularity** — relative-offset clamp range + barriers-left bucketing (PLAN §3). Start coarse; it's optional per §8 — do not over-engineer.
3. **Train now vs ship placeholder table** — DECISION says build all now (C2 runs `train.py` this step). Confirm training fits the session budget; otherwise ship a small placeholder `qtable.json` and defer a full train.
4. **Record the 5×5 forced-Cop-win / barrier-inert finding in the README** (DECISION §4, PRD §4) — flagged as a genuine insight for the grader.

> Once approved, `/relay-next` transcribes these TODOs into code one box at a time, and `/relay-verify <hash>` holds each box to the Segal §19.1 Table-5 gate (ruff, pytest, coverage ≥85%, ≤150 lines/file, no hard-coded values, no secrets, uv-only).
