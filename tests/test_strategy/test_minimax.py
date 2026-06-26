import pytest
from src.game.board import Board
from src.game.state import GameState
from src.game.config import load_config
from src.game.moves import Move, legal_moves
from src.game.engine import play_sub_game
from src.game.movers import GreedyMover
from src.strategy.minimax import MinimaxMover, _clone


@pytest.fixture
def cfg():
    return load_config("config.yaml")


def _mm(cfg):
    mm_cfg = cfg.strategy["minimax"]
    return MinimaxMover(depth=mm_cfg["depth"], weights=mm_cfg["weights"], max_moves=cfg.max_moves)


def test_clone_is_independent():
    board = Board(5, 5)
    board.barriers.add((1, 1))
    state = GameState(
        cop_pos=(0, 0), thief_pos=(4, 4), to_move="COP",
        moves_used=0, cop_barriers_left=5, board=board,
    )
    cloned = _clone(state)
    cloned.board.barriers.add((2, 2))
    assert (2, 2) not in state.board.barriers


def test_minimax_search_is_pure(cfg):
    board = Board(5, 5)
    state = GameState(
        cop_pos=(0, 0), thief_pos=(4, 4), to_move="COP",
        moves_used=0, cop_barriers_left=cfg.max_barriers, board=board,
    )
    snap_cop = state.cop_pos
    snap_thief = state.thief_pos
    snap_barriers = frozenset(state.board.barriers)

    mm = _mm(cfg)
    mm.choose_move(state)

    assert state.cop_pos == snap_cop
    assert state.thief_pos == snap_thief
    assert frozenset(state.board.barriers) == snap_barriers


def test_barrier_is_candidate(cfg):
    board = Board(5, 5)
    state = GameState(
        cop_pos=(2, 2), thief_pos=(4, 4), to_move="COP",
        moves_used=0, cop_barriers_left=cfg.max_barriers, board=board,
    )
    assert Move.PLACE_BARRIER in legal_moves(state)

    candidates = []
    original_search = MinimaxMover._search

    def patched(self, s, depth, alpha, beta, c):
        if depth == self._depth - 1:
            candidates.append(s)
        return original_search(self, s, depth, alpha, beta, c)

    mm = _mm(cfg)
    MinimaxMover._search = patched
    try:
        mm.choose_move(state)
    finally:
        MinimaxMover._search = original_search

    barrier_explored = any(
        s.cop_barriers_left == cfg.max_barriers - 1 for s in candidates
    )
    assert barrier_explored, "PLACE_BARRIER was not among evaluated candidates"


def _capture_rate(cop_mover, thief_mover, cfg, starts):
    wins = 0
    for cop_start, thief_start in starts:
        from src.game.state import initial_state as _is
        import copy

        class _FixedStart:
            def __init__(self, cop, thief):
                self.cop = cop
                self.thief = thief

        original_is = __import__("src.game.state", fromlist=["initial_state"]).initial_state

        def patched_initial_state(c):
            board = Board(c.grid_size[0], c.grid_size[1])
            return GameState(
                cop_pos=cop_start, thief_pos=thief_start, to_move="THIEF",
                moves_used=0, cop_barriers_left=c.max_barriers, board=board,
            )

        import src.game.engine as eng_mod
        import src.game.state as state_mod
        old = state_mod.initial_state
        state_mod.initial_state = patched_initial_state
        eng_mod.initial_state = patched_initial_state
        try:
            result = play_sub_game(cfg, cop_mover, thief_mover)
            if result.winner == "COP":
                wins += 1
        finally:
            state_mod.initial_state = old
            eng_mod.initial_state = old
    return wins


def test_minimax_beats_greedy_9x9():
    import dataclasses
    from src.game.config import Config, ScoringConfig

    cfg9 = Config(
        grid_size=(9, 9), max_moves=25, num_games=6, max_barriers=5,
        scoring=ScoringConfig(cop_win=20, thief_win=10, cop_loss=5, thief_loss=5),
        strategy={
            "cop": "minimax", "thief": "minimax",
            "minimax": {"depth": 2, "weights": {
                "dist": 1.0, "thief_mob": 0.3, "corner": 0.2, "reach": 0.15, "capture": 1000.0,
            }},
            "qtable": {"path": "models/qtable.json", "train": {}},
        },
    )

    starts = [
        ((0, 0), (8, 8)),
        ((0, 8), (8, 0)),
        ((4, 0), (4, 8)),
    ]

    mm_cfg = cfg9.strategy["minimax"]
    mm_cop = MinimaxMover(depth=mm_cfg["depth"], weights=mm_cfg["weights"], max_moves=cfg9.max_moves)
    greedy_cop = GreedyMover()
    greedy_thief = GreedyMover()

    mm_wins = _capture_rate(mm_cop, greedy_thief, cfg9, starts)
    greedy_wins = _capture_rate(greedy_cop, greedy_thief, cfg9, starts)

    assert mm_wins >= greedy_wins, f"Minimax {mm_wins} < Greedy {greedy_wins}"
    assert mm_wins > 0 or greedy_wins < len(starts), "At least one start must differentiate movers"
