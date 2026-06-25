# TODO ג€” Step 1: Game logic & rules

> Implements `PRD_step1_game_logic.md` + `PLAN_step1_game_logic.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[x]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename.
3. **Never hard-code** game parameters ג€” read them from `config.yaml`.
4. Do not assume a 5ֳ—5 grid; read `grid_size` from config.
5. If a box seems ambiguous, STOP and ask ג€” do not guess.
6. Keep each file focused; do not add features not listed here.
7. **Run every command from the repository root** (the folder containing `config.yaml`).

## Conventions
- Language/runtime: Python 3.12
- Source root: `src/` ֲ· Tests: `tests/`
- Each box format: **ID ֲ· file ֲ· action ֲ· detail ֲ· Check.**
- **Single source of truth for barriers:** the `Board` object. `GameState` holds a
  reference to the `Board`; it does NOT keep its own separate barrier set.
- **The 8 movement directions** are these exact `(d_row, d_col)` deltas:
  `N(-1,0) S(1,0) E(0,1) W(0,-1) NE(-1,1) NW(-1,-1) SE(1,1) SW(1,-1)`.
- **Starting positions (deterministic):** Cop at `(0, 0)`; Thief at
  `(rows-1, cols-1)`. They are always distinct for any grid ג‰¥ 2ֳ—2.
- **Roles / turn:** `to_move` is the string `"THIEF"` or `"COP"`. The **Thief moves
  first** every sub-game.

---

## Phase A ג€” setup & dependencies
- [x] **A1** ג€” `requirements.txt` ג€” create ג€” list runtime + test deps, one per line:
      `pyyaml` and `pytest`. Then install: `pip install -r requirements.txt`.
      **Check:** `python -c "import yaml, pytest"` exits 0.
- [x] **A2** ג€” `pyproject.toml` ג€” create ג€” add a minimal pytest config so imports resolve
      from the repo root:
      ```toml
      [tool.pytest.ini_options]
      pythonpath = ["."]
      ```
      **Check:** the file exists and `python -c "import tomllib,1 if False else 0"` exits 0
      (or simply confirm the file is present and valid TOML).
- [x] **A3** ג€” `config.yaml` ג€” create ג€” add root-level game parameters:
      ```yaml
      grid_size: [5, 5]
      max_moves: 25
      num_games: 6
      max_barriers: 5
      scoring:
        cop_win: 20
        thief_win: 10
        cop_loss: 5
        thief_loss: 5
      ```
      **Check:** file is valid YAML ג€” `python -c "import yaml; yaml.safe_load(open('config.yaml'))"` exits 0.
- [x] **A4** ג€” `src/game/__init__.py` ג€” create ג€” empty file to make `src.game` an importable package.
      **Check:** `python -c "import src.game"` exits 0 (run from repo root).

## Phase B ג€” config & models
- [x] **B1** ג€” `src/game/config.py` ג€” create ג€” define `ScoringConfig` and `Config` dataclasses
      and implement `def load_config(path: str) -> Config:`.
      `Config` fields: `grid_size: tuple[int,int]`, `max_moves: int`, `num_games: int`,
      `max_barriers: int`, `scoring: ScoringConfig`.
      `ScoringConfig` fields: `cop_win`, `thief_win`, `cop_loss`, `thief_loss` (all `int`).
      `load_config` reads the YAML, converts `grid_size` to a 2-tuple, and **validates**:
      `grid_size` is two positive ints, `max_moves > 0`, `num_games > 0`,
      `max_barriers >= 0`, all scoring values `>= 0`; raise `ValueError` otherwise.
      **Check:** `python -c "from src.game.config import load_config; print(load_config('config.yaml'))"` exits 0.
- [x] **B2** ג€” `src/game/board.py` ג€” create ג€” implement `class Board` constructed as
      `Board(rows: int, cols: int)`, holding `rows`, `cols`, and `barriers: set[tuple[int,int]]`.
      Methods: `in_bounds(pos) -> bool` (inside the grid), `is_blocked(pos) -> bool`
      (a barrier is on `pos`), `place_barrier(pos) -> None` (reject out-of-bounds; reject a
      position that already has a barrier by raising `ValueError`).
      **Check:** `python -c "from src.game.board import Board; b=Board(5,5); b.place_barrier((2,2)); print(b.is_blocked((2,2)), b.in_bounds((9,9)))"` prints `True False`.
- [x] **B3** ג€” `src/game/state.py` ג€” create ג€” define `GameState` dataclass with fields:
      `cop_pos: tuple[int,int]`, `thief_pos: tuple[int,int]`, `to_move: str`,
      `moves_used: int`, `cop_barriers_left: int`, `board: Board`.
      (Barriers live on `board`; do NOT add a separate barrier set here.)
      **Check:** `python -c "from src.game.state import GameState; from src.game.board import Board; print(GameState((0,0),(4,4),'THIEF',0,5,Board(5,5)))"` exits 0.
- [x] **B4** ג€” `src/game/state.py` ג€” extend ג€” add `def initial_state(config) -> GameState:`
      that builds a fresh `Board(*config.grid_size)`, places Cop at `(0,0)`, Thief at
      `(rows-1, cols-1)`, `to_move="THIEF"`, `moves_used=0`, `cop_barriers_left=config.max_barriers`.
      **Check:** `python -c "from src.game.config import load_config; from src.game.state import initial_state; s=initial_state(load_config('config.yaml')); print(s.cop_pos, s.thief_pos, s.to_move)"` prints `(0, 0) (4, 4) THIEF`.

## Phase C ג€” moves & rules
- [x] **C1** ג€” `src/game/moves.py` ג€” create ג€” define `class Move(Enum)` with the 8 directional
      members (`N,S,E,W,NE,NW,SE,SW`) whose values are the exact `(d_row,d_col)` deltas listed in
      Conventions, plus a `PLACE_BARRIER` member. Add a helper
      `def _target(pos, move) -> tuple[int,int]:` returning the destination cell for a directional
      move (undefined for `PLACE_BARRIER`).
      **Check:** `python -c "from src.game.moves import Move; print(Move.NE.value, len(list(Move)))"` prints `(-1, 1) 9`.
- [x] **C2** ג€” `src/game/moves.py` ג€” extend ג€” implement
      `def legal_moves(state) -> list[Move]:` for the current player (`state.to_move`):
      include each directional `Move` whose target is `in_bounds` and **not** `is_blocked`;
      additionally, if the current player is `"COP"` **and** `state.cop_barriers_left > 0`,
      include `Move.PLACE_BARRIER`. The Thief never gets `PLACE_BARRIER`.
      **Check:** `python -c "from src.game.config import load_config; from src.game.state import initial_state; from src.game.moves import legal_moves; print(len(legal_moves(initial_state(load_config('config.yaml'))))>0)"` prints `True`.
- [x] **C3** ג€” `src/game/moves.py` ג€” extend ג€” implement
      `def apply_move(state, move) -> GameState:` returning a **new** `GameState` (do not mutate
      the input). Rules: for a directional move, move the current player to `_target`. For
      `PLACE_BARRIER` (Cop only): call `state.board.place_barrier(state.cop_pos)`, decrement
      `cop_barriers_left`, and **the Cop does NOT change cell**. In all cases increment
      `moves_used` by 1 and flip `to_move` (`THIEF`ג†”`COP`). Raise `ValueError` if `move` is not in
      `legal_moves(state)`.
      **Check:** `python -c "from src.game.config import load_config; from src.game.state import initial_state; from src.game.moves import apply_move,legal_moves; s=initial_state(load_config('config.yaml')); ns=apply_move(s,legal_moves(s)[0]); print(ns.moves_used, ns.to_move)"` prints `1 COP`.
- [x] **C4** ג€” `src/game/rules.py` ג€” create ג€” implement
      `def is_capture(state) -> bool:` (`cop_pos == thief_pos`),
      `def is_timeout(state, config) -> bool:` (`state.moves_used >= config.max_moves`),
      and `def score_sub_game(winner: str, config) -> tuple[int,int]:` returning
      `(cop_score, thief_score)` = `(cop_win, thief_loss)` if `winner=="COP"` else
      `(cop_loss, thief_win)`.
      **Check:** `python -c "from src.game.config import load_config; from src.game.rules import score_sub_game; c=load_config('config.yaml'); print(score_sub_game('COP',c), score_sub_game('THIEF',c))"` prints `(20, 5) (5, 10)`.

## Phase D ג€” movers
- [x] **D1** ג€” `src/game/movers.py` ג€” create ג€” declare `class Mover(Protocol):` with
      `def choose_move(self, state: GameState) -> Move: ...`, and implement
      `class RandomMover:` whose `choose_move` returns `random.choice(legal_moves(state))`.
      It may assume `legal_moves(state)` is non-empty (the engine never calls a mover when it is empty).
      **Check:** `python -c "from src.game.movers import RandomMover; from src.game.config import load_config; from src.game.state import initial_state; print(RandomMover().choose_move(initial_state(load_config('config.yaml'))))"` exits 0.

## Phase E ג€” results & engine
- [x] **E1** ג€” `src/game/engine.py` ג€” create ג€” define two dataclasses at the top of the file:
      `SubGameResult(winner: str, cop_score: int, thief_score: int, moves_used: int)` and
      `SeriesResult(sub_games: list[SubGameResult], cop_total: int, thief_total: int)`.
      **Check:** `python -c "from src.game.engine import SubGameResult, SeriesResult; print(SubGameResult('COP',20,5,3))"` exits 0.
- [x] **E2** ג€” `src/game/engine.py` ג€” extend ג€” implement
      `def play_sub_game(config, cop_mover, thief_mover) -> SubGameResult:`.
      Build `initial_state(config)`. Loop:
      (a) if `is_capture(state)` ג†’ winner `"COP"`, break;
      (b) if `is_timeout(state, config)` ג†’ winner `"THIEF"`, break;
      (c) compute `legal_moves(state)`; **if empty, skip this player's turn** by incrementing
      `moves_used` and flipping `to_move` (do not call the mover);
      (d) otherwise pick `cop_mover` or `thief_mover` per `state.to_move`, get a move, and
      `state = apply_move(state, move)`.
      After the loop, `cop_score, thief_score = score_sub_game(winner, config)` and return a
      `SubGameResult(winner, cop_score, thief_score, state.moves_used)`.
      **Check:** `python -c "from src.game.config import load_config; from src.game.movers import RandomMover; from src.game.engine import play_sub_game; r=play_sub_game(load_config('config.yaml'),RandomMover(),RandomMover()); print(r.winner in ('COP','THIEF'))"` prints `True`.
- [x] **E3** ג€” `src/game/engine.py` ג€” extend ג€” implement
      `def play_series(config, cop_mover, thief_mover) -> SeriesResult:` that runs
      `config.num_games` sub-games, collects each `SubGameResult`, and sums `cop_total`/`thief_total`.
      **Check:** `python -c "from src.game.config import load_config; from src.game.movers import RandomMover; from src.game.engine import play_series; r=play_series(load_config('config.yaml'),RandomMover(),RandomMover()); print(len(r.sub_games), r.cop_total+r.thief_total)"` prints `6` and a positive total.
- [x] **E4** ג€” `src/game/__main__.py` ג€” create ג€” a CLI entry: load `config.yaml`, run
      `play_series` with two `RandomMover`s, and print each sub-game result plus the series totals.
      **Check:** `python -m src.game` runs from repo root, prints 6 sub-game lines and a totals line, exits 0.

## Phase F ג€” tests
- [x] **F1** ג€” `tests/test_game/__init__.py` ג€” create ג€” empty file so the test package imports.
      **Check:** file exists.
- [x] **F2** ג€” `tests/test_game/test_config.py` ג€” create ג€” assert `load_config('config.yaml')`
      returns the expected typed values, and that an invalid grid (e.g. `grid_size=[0,5]`) raises `ValueError`.
      **Check:** `pytest tests/test_game/test_config.py -q` passes.
- [x] **F3** ג€” `tests/test_game/test_board.py` ג€” create ג€” assert `in_bounds`/`is_blocked` behave,
      that `place_barrier` rejects duplicates, and that a barrier cell is excluded from `legal_moves`
      for a player adjacent to it (blocks both players).
      **Check:** `pytest tests/test_game/test_board.py -q` passes.
- [x] **F4** ג€” `tests/test_game/test_rules.py` ג€” create ג€” assert `is_capture` true when positions
      match, `is_timeout` true at `max_moves`, and `score_sub_game` returns `(20,5)` for COP and `(5,10)` for THIEF.
      **Check:** `pytest tests/test_game/test_rules.py -q` passes.
- [x] **F5** ג€” `tests/test_game/test_moves.py` ג€” create ג€” assert movement is 8-directional, that an
      **out-of-bounds / barrier-cell move is rejected** by `apply_move` (raises `ValueError`), that the
      Thief never receives `PLACE_BARRIER` in `legal_moves`, and that the Cop loses `PLACE_BARRIER`
      once `cop_barriers_left == 0`.
      **Check:** `pytest tests/test_game/test_moves.py -q` passes.
- [x] **F6** ג€” `tests/test_game/test_engine.py` ג€” create ג€” parameterize over grid sizes
      `[(2,2),(3,3),(4,4),(5,5)]`: build a config per size (load base config, override `grid_size`),
      run `play_series`, and assert it returns `num_games` sub-games and that every
      sub-game total equals either `cop_win+thief_loss` or `cop_loss+thief_win`.
      Also assert a forced capture yields `cop_score == config.scoring.cop_win`.
      **Check:** `pytest tests/test_game/test_engine.py -q` passes.
- [x] **F7** ג€” full suite ג€” run everything and confirm no hard-coded game constants leaked.
      **Check:** `pytest -q` passes AND grep finds no stray game literals in engine code:
      `grep -rnE "\b(25|20|10|\[5, 5\])\b" src/game | grep -v config.py` returns nothing meaningful.

## Phase G ג€” verify
- [x] **G1** ג€” `config.yaml` ג€” verify ג€” confirm it still contains the exact required keys/defaults
      and the whole pipeline runs.
      **Check:** `python -m src.game` exits 0 and `pytest -q` passes.

---

## Definition of Done
- [x] Every box above is ticked and its Check passed.
- [x] All PRD acceptance criteria hold (`PRD_step1_game_logic.md` ֲ§7).
- [x] No hard-coded game parameters anywhere in the step's code.
- [x] `python -m src.game` runs a full 6-sub-game series from the command line.
- [x] `docs/_system/ROADMAP.md` is updated to mark step 1 as ג… (Developer does this at the end).
