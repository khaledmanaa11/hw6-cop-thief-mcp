# PLAN — Step 1: Game logic & rules

- **Status:** triplet-built
- **Source:** `DECISION_step1_game_logic.md`, `PRD_step1_game_logic.md`

## 1. Architecture overview
This step builds a pure Python game engine under `src/game/` that is driven by a root `config.yaml`. The engine is layered: config loading → board and state representation → legal move generation → rule evaluation → mover interface → sub-game/series runner. The later MCP and agent steps consume the `choose_move(state)` seam and the plain result objects returned by `play_sub_game` and `play_series`.

## 2. File / module layout
```
requirements.txt                     (new)   — pyyaml, pytest
pyproject.toml                       (new)   — pytest pythonpath = ["."]
config.yaml                          (new)   — game parameter defaults
src/game/__init__.py                 (new)   — package marker
src/game/config.py                   (new)   — typed config loader + validation
src/game/board.py                    (new)   — board grid, barriers (single source), bounds checks
src/game/state.py                    (new)   — `GameState` + `initial_state(config)`
src/game/moves.py                    (new)   — directions, `legal_moves`, `apply_move`
src/game/rules.py                    (new)   — capture/timeout detection and scoring
src/game/movers.py                   (new)   — `Mover` protocol + `RandomMover`
src/game/engine.py                   (new)   — `SubGameResult`, `SeriesResult`, `play_sub_game`, `play_series`
src/game/__main__.py                 (new)   — CLI entry: run a series with RandomMovers
tests/test_game/__init__.py          (new)   — test package marker
tests/test_game/test_config.py       (new)   — config loader + validation tests
tests/test_game/test_board.py        (new)   — bounds/barrier rule tests
tests/test_game/test_rules.py        (new)   — capture/timeout/scoring tests
tests/test_game/test_moves.py        (new)   — 8-dir, illegal-move rejection, barrier-action rules
tests/test_game/test_engine.py       (new)   — series and grid escalation tests
```

## 3. Data model / key structures
- `Config` — `grid_size: tuple[int, int]`, `max_moves: int`, `num_games: int`, `max_barriers: int`, `scoring: ScoringConfig`.
- `ScoringConfig` — `cop_win: int`, `thief_win: int`, `cop_loss: int`, `thief_loss: int`.
- `Position` — `(row: int, col: int)` tuple.
- `Move` — enum values for 8 movement directions plus `PLACE_BARRIER`.
- `GameState` — `cop_pos`, `thief_pos`, `to_move`, `moves_used`, `cop_barriers_left`, `board: Board`. **Barriers live only on `Board`** (single source of truth); `GameState` references the board rather than keeping its own barrier set. Built via `initial_state(config)` (Cop `(0,0)`, Thief `(rows-1, cols-1)`, Thief to move).
- `SubGameResult` — `winner: str` (winning ROLE), `cop_score: int`, `thief_score: int`, `moves_used: int`, `cop_group: str`, `thief_group: str` (which GROUP "A"/"B" played each role).
- `SeriesResult` — `sub_games: list[SubGameResult]`, `group_a_total: int`, `group_b_total: int`. Per §4.4 each group plays Cop in half the sub-games and Thief in the other half; a group's total = its Cop points + its Thief points (max 90, min 30).

## 4. Component design
### `src/game/config.py`
- Responsibility: load YAML and validate game parameters.
- Key functions:
  - `def load_config(path: str) -> Config:` — read YAML, validate required keys, convert `grid_size` to tuple, reject invalid values.

### `src/game/board.py`
- Responsibility: represent the resizable board and barrier occupancy.
- Key classes/functions:
  - `class Board:` — stores `rows`, `cols`, `barriers: set[Position]`.
  - `def in_bounds(self, pos: Position) -> bool:` — true inside the grid.
  - `def is_blocked(self, pos: Position) -> bool:` — true if barrier present.
  - `def place_barrier(self, pos: Position) -> None:` — add barrier and reject duplicates.

### `src/game/state.py`
- Responsibility: store the current game snapshot.
- Key structures:
  - `class GameState:` — all mutable game state fields, including positions, turn, move count, and barrier budget.

### `src/game/moves.py`
- Responsibility: define moves and compute legal options.
- Key functions:
  - `enum Move` — 8 direction actions plus `PLACE_BARRIER`.
  - `def legal_moves(state: GameState) -> list[Move]:` — return allowed actions for current player.
  - `def apply_move(state: GameState, move: Move) -> GameState:` — return next state snapshot.

### `src/game/rules.py`
- Responsibility: detect end conditions and score results.
- Key functions:
  - `def is_capture(state: GameState) -> bool:` — true when Cop and Thief share a cell.
  - `def is_timeout(state: GameState, config: Config) -> bool:` — true when `moves_used >= max_moves`.
  - `def score_sub_game(winner: str, config: Config) -> tuple[int, int]:` — return cop and thief scores.

### `src/game/movers.py`
- Responsibility: define the mover seam.
- Key types:
  - `class Mover(Protocol):` — `def choose_move(self, state: GameState) -> Move`.
  - `class RandomMover:` — implements `choose_move` by sampling legal moves.

### `src/game/engine.py`
- Responsibility: define result objects and run sub-games and series.
- Key types/functions:
  - `SubGameResult` / `SeriesResult` — plain dataclasses (downstream contract for steps 6 & 8).
  - `def play_sub_game(config: Config, cop_mover: Mover, thief_mover: Mover) -> SubGameResult:` — run a single sub-game with Thief moving first. If the current player has **no legal moves**, that turn is skipped (count it, flip turn) rather than calling the mover — this prevents a crash when a player is boxed in by barriers/edges.
  - `def play_series(config: Config, group_a: Mover, group_b: Mover) -> SeriesResult:` — run `num_games` sub-games between two **groups**, swapping Cop/Thief roles each sub-game (even → A=Cop/B=Thief, odd → A=Thief/B=Cop), and accumulate each group's total (its Cop points + its Thief points). Matches §4.4's 90-max/30-min group bound.

### `src/game/__main__.py`
- Responsibility: command-line entry so the series runs end-to-end (`python -m src.game`).
- Loads `config.yaml`, runs `play_series` with two `RandomMover`s, prints per-sub-game results and the accumulated totals.

## 5. Control flow / sequences
1. Load `Config` from `config.yaml`.
2. Build the initial `GameState` via `initial_state(config)` (Cop `(0,0)`, Thief `(rows-1,cols-1)`, Thief to move, barrier budget = `max_barriers`).
3. In `play_sub_game`, loop while neither capture nor timeout has occurred:
   - Compute `legal_moves(state)`. **If empty, skip the turn** (increment `moves_used`, flip `to_move`) — do not call the mover.
   - Otherwise ask `thief_mover.choose_move(state)` when `to_move == "THIEF"`, else `cop_mover.choose_move(state)`.
   - `apply_move(state, move)` validates against `legal_moves` (raises `ValueError` on an illegal move), increments `moves_used`, and switches turn.
4. When the game ends, compute `SubGameResult` using the scoring rules.
5. In `play_series`, repeat the sub-game loop `config.num_games` times. Each sub-game swaps which group is Cop vs Thief; attribute each role's points to the group that played it, accumulating `group_a_total` and `group_b_total`.

## 6. Config additions
| Key | Default | Used by |
|-----|---------|---------|
| `grid_size` | `[5, 5]` | `src/game/board.py`, `src/game/config.py`, `src/game/engine.py` |
| `max_moves` | `25` | `src/game/engine.py`, `src/game/rules.py` |
| `num_games` | `6` | `src/game/engine.py` |
| `max_barriers` | `5` | `src/game/moves.py`, `src/game/state.py` |
| `scoring.cop_win` | `20` | `src/game/rules.py` |
| `scoring.thief_win` | `10` | `src/game/rules.py` |
| `scoring.cop_loss` | `5` | `src/game/rules.py` |
| `scoring.thief_loss` | `5` | `src/game/rules.py` |

## 7. Test strategy
- **Unit:** validate `load_config`, board bounds and barriers, move legality, capture/timeout detection, and scoring values.
- **Integration:** run `play_sub_game` and `play_series` with `RandomMover` on 5×5 and smaller grids.
- **Sanity-grid escalation:** explicit tests for 2×2, 3×3, 4×4, and 5×5 to prove generic board support.

## 8. Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Hard-coding game constants | medium | centralize values in `config.yaml`; validate code only reads config keys. |
| Barrier semantics misapplied | medium | test Cop barrier placement consumes turn and blocks both players. |
| Turn-order mistake | low | enforce Thief first in `play_sub_game` and cover with tests. |
| Result object mismatch | low | keep `SubGameResult` and `SeriesResult` simple dataclasses and validate against acceptance criteria. |

## 9. Work breakdown (macro order)
1. Define `config.yaml` and typed config loader.
2. Implement board and state models.
3. Implement move actions and legal-move checking.
4. Implement rules and scoring.
5. Implement engine loops for sub-game and series execution.
6. Add tests for rules and grid escalation.
7. Validate with `pytest` and confirm no hard-coded game constants.
