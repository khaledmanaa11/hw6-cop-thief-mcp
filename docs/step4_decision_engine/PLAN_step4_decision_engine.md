# PLAN — Step 4: Decision Engine (strategy brain)

- **Status:** triplet-built
- **Source:** `DECISION_step4_decision_engine.md`, `PRD_step4_decision_engine.md`
- **Cross-links:** `PRD_step4_decision_engine.md` (requirements) · `TODO_step4_decision_engine.md` (atomic build order)

## 1. Architecture (C4 / the seam)
A new **strategy / brain tier** (`src/strategy/`) sits behind the *unchanged* `Mover` seam
(`choose_move(state) -> Move`). Step 3 already speaks to that seam: `engine.play_sub_game` /
`play_series` and the orchestrator's `run_series` take `Mover` objects. Step 4 only changes which
object is handed in — produced by **one factory**, `build_mover(role, config)`. Every brain is a pure
function of `(config, state)`: it imports the Step-1 engine for legality/expansion/terminals and adds
*only* search + evaluation (or, for the Q-table, a learned-value lookup). The MCP servers and the
referee are **not touched**.

```
   engine.play_series / orchestrator.run_series  (Step 3 — UNCHANGED)
                 │  takes Mover objects
                 ▼
        build_mover(role, config)   ── src/strategy/factory.py
                 │
     ┌───────────┼─────────────┬───────────────┐
     ▼           ▼             ▼               ▼
 MinimaxMover  QTableMover  GreedyMover    RandomMover
 (minimax.py)  (qtable.py)  (Step 3)       (Step 1)
     │            │
     │ leaf value │ loads models/qtable.json (committed)
     ▼            ▲
 evaluate.py      └── src/strategy/train.py  (offline, seeded, run ONCE)
     │
     ▼  reuses, never re-implements
 src/game/{engine,state,moves,rules,board,config,movers}.py  (Step-1 engine)
```

The factory is the **seam**; the engine is **reused** (`legal_moves`, `apply_move`, `is_capture`,
`is_timeout`); the only new logic is the alpha-beta search, the heuristic, and the Q-table
load/argmax. `MinimaxMover` is the substance of the step.

## 2. Public interface (stable contract)
```python
# src/strategy/evaluate.py
def evaluate(state: GameState, config) -> float: ...      # Cop's perspective: + = good for Cop

# src/strategy/minimax.py
class MinimaxMover:                                        # one class, both roles
    def __init__(self, depth: int, weights: dict): ...
    def choose_move(self, state: GameState) -> Move: ...   # alpha-beta; Cop=MAX, Thief=MIN

# src/strategy/qtable.py
class QTableMover:
    def __init__(self, table_path: str): ...
    def choose_move(self, state: GameState) -> Move: ...   # argmax over legal moves, det. tie-break

# src/strategy/train.py
def train(config, out_path: str) -> None: ...              # seeded self-play → writes qtable JSON

# src/strategy/factory.py
def build_mover(role: str, config) -> Mover: ...           # minimax|qtable|greedy|random
```
Every brain satisfies the existing `Mover` protocol from `src/game/movers.py`, so the orchestrator and
engine consume them with **zero** changes.

## 3. Data model / key structures
- **Reused unchanged:** `GameState`, `Move` (king-move deltas + `PLACE_BARRIER`), `Board`,
  `legal_moves`, `apply_move`, `is_capture`, `is_timeout`, `score_sub_game`, `initial_state`,
  `SubGameResult`/`SeriesResult`, and the `Mover` protocol.
- **State clone helper** (`_clone(state) -> GameState`, in `minimax.py`): deep-copies `GameState` *and*
  a fresh `Board` (copy `rows`, `cols`, `set(barriers)`). **Load-bearing:** `apply_move(state,
  PLACE_BARRIER)` calls `board.place_barrier(...)` which **mutates the shared `Board`** (the returned
  `GameState` reuses the same `board` reference), so every search child must expand on a clone or the
  live game and sibling branches corrupt. R-AC4 tests exactly this.
- **Evaluation features** (`evaluate`): Chebyshev `cop↔thief` distance, thief open-neighbour count,
  thief corner pressure, thief reachable area (BFS within remaining ply budget, walls block). Terminal
  shortcuts: capture → `+CAP - moves_used`; timeout → `-CAP + moves_used`. Weights pulled from
  `config.strategy.minimax.weights` (`dist`, `thief_mob`, `corner`, `reach`, `capture`).
- **Q-table** (`models/qtable.json`): JSON dict keyed by a compact, **board-size-agnostic** abstract
  state → `{move_name: q}`. Key abstraction = `(clamped Δrow, clamped Δcol between self and opponent,
  to_move, barriers_left_bucket)`. Documented in `qtable.py`. On an unseen key, fall back to
  greedy/first-legal.
- **Config:** new top-level optional block (PRD §2). Parsed into a `Config.strategy` field (trailing
  optional, default a sensible minimax-both), same backward-compatible pattern as `servers`/`output`:
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

## 4. File layout (each ≤150 lines, §3.2)
- `src/strategy/__init__.py` (new) — make `src.strategy` importable.
- `src/strategy/evaluate.py` (new) — `evaluate(state, config) -> float`; pure feature heuristic +
  terminal shortcuts; weights from `config.strategy.minimax.weights`. No literal game numbers.
- `src/strategy/minimax.py` (new) — `MinimaxMover` (alpha-beta; Cop=MAX, Thief=MIN; candidates =
  `legal_moves` incl. `PLACE_BARRIER`; `_clone` per node; deterministic tie-break) + the clone helper.
  This is the densest file — give the Developer the search loop as copy-paste code.
- `src/strategy/qtable.py` (new) — `QTableMover` (load JSON, abstract-state key, argmax, fallback).
- `src/strategy/train.py` (new) — offline seeded ε-greedy self-play trainer; random starts; writes
  `models/qtable.json`. Runtime never imports this.
- `src/strategy/factory.py` (new) — `build_mover(role, config) -> Mover`; unknown name → clear error.
- `models/qtable.json` (new, **committed** — do NOT gitignore) — trained table so a fresh checkout runs
  `qtable` without training.
- `src/game/config.py` (edit) — add optional trailing `strategy` field + conditional `strategy:`
  parsing (default minimax-both if absent).
- `config.yaml` (edit) — add the `strategy:` block above.
- `tests/test_strategy/__init__.py` (new) + test modules (new) — see TODO coverage matrix; run on the
  2×2…5×5 ladder, port-free (no servers needed — strategy is engine-only).

## 5. ADRs — decision + rationale + alternatives (§2.2)
- **ADR-1 — Config-selectable `Mover` family behind the one seam.** · Rationale: the assignment says
  strategy isn't graded (§2/§3) — the brain must be *correct, swappable, config-driven*; one factory
  means the orchestrator (Step 3) and servers (Step 2) need **zero** changes and Step 5 can wrap the same
  movers. · Rejected: hard-wiring a single brain into the orchestrator — couples strategy to wiring,
  blocks A/B comparison and the bonus.
- **ADR-2 — Minimax / alpha-beta as the primary brain, one class for both roles.** · Rationale: the
  sub-game is zero-sum pursuit, so Cop=MAX / Thief=MIN over one shared `evaluate` is the natural model;
  it's the strongest brain we can ship today for the bonus and dominates greedy on non-trivial boards. ·
  Rejected: separate Cop/Thief search classes — duplicate logic, two places to drift.
- **ADR-3 — Clone `GameState` + `Board` per search node.** · Rationale: `apply_move` mutates the shared
  `Board` on `PLACE_BARRIER`; without cloning, the search corrupts the live game and sibling branches
  (R-AC4). · Rejected: undo-move / make-unmake — fragile against the barrier mutation and harder to keep
  pure; clone is simpler and the depth/branching are small.
- **ADR-4 — Minimax considers `PLACE_BARRIER` as a legal candidate.** · Rationale: honesty — the search
  *may* wall when beneficial; it legally can even if (empirically) it rarely does under 8-dir movement. ·
  Rejected: excluding barriers from candidates — would hide a legal option and contradict the "search the
  real game tree" claim.
- **ADR-5 — Tabular Q-Learning, trained offline, committed table.** · Rationale: §8 recommends tabular
  Q-learning (optional); a board-size-agnostic relative-offset key generalizes across the ladder; a
  committed `models/qtable.json` means a fresh checkout runs `qtable` with no training, and `train.py` is
  the reproducer not a runtime dep. · Rejected: deep/neural Q-network (**§8 limits to tabular**); train
  at runtime (slow, non-deterministic, needless).
- **ADR-6 — Keep barriers + movement exactly as locked; document the cop-number finding.** · Rationale:
  §4.2 mandates 8-dir and §4.3 fixes the barrier rule; playtesting shows 5×5 is a forced Cop win and an
  optimal Cop places 0 barriers even with free walls — so we keep the rules correct, let the search
  consider them, and **document** the analysis (a genuine insight for the grader/README). · Rejected:
  switching to 4-dir or changing the wall rule to make barriers matter — violates §4.2/§4.3 and breaks
  interop.

## 6. Concurrency / gatekeeper / config notes
- **No new concurrency:** brains are synchronous, pure `(config, state) -> Move` functions; the existing
  `async` orchestrator calls `choose_move` synchronously inside each ply exactly as it does for
  `GreedyMover`. §15 not triggered.
- **Search purity is the gatekeeper invariant:** all expansion happens on clones; the live `GameState`
  the orchestrator owns is never mutated by a brain. This is what keeps the validate-before-apply loop
  (Step 3) honest.
- **Determinism (§7):** minimax fixed tie-break (first best in `Move` enum order, no RNG); Q-table
  runtime argmax deterministic; the **only** RNG is seeded inside `train.py`. Replays stay reproducible
  exactly as Step 3.
- **Config-driven / resizable (§7.2, §4.5):** brain names, depth, weights, qtable path/params all from
  `config.strategy`; grid bounds always from `state.board.rows/cols`. **No literal game numbers**
  (`5`/`25`/`8`/board coords) in `src/strategy/` — TODO ends with a grep gate.
- **Engine reuse, not re-implementation:** candidates come from `legal_moves(state)`; expansion uses
  `apply_move` on the **clone**; terminals use `is_capture`/`is_timeout`; scoring uses
  `score_sub_game`. The only new code is search + evaluation + Q-table I/O.
- **`{TBD}` for the Director (resolve before/at build):** (1) **Q-table abstraction granularity** — the
  relative-offset clamp range and barriers-left bucketing (start coarse; it's optional per §8, don't
  over-engineer). (2) **Minimax default depth** — `4` proposed; confirm it keeps a full series fast on
  the target machine. (3) **Whether to train the Q-table this step or ship a placeholder table** — DECISION
  says build all now; confirm `train.py` runs within session budget.
