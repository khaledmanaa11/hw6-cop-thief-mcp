from src.game.board import Board
from src.game.state import GameState
from src.game.rules import is_capture, is_timeout, score_sub_game
from src.game.config import load_config


def _make_state(cop_pos, thief_pos, moves_used=0):
    return GameState(cop_pos=cop_pos, thief_pos=thief_pos, to_move="THIEF",
                     moves_used=moves_used, cop_barriers_left=5, board=Board(5, 5))


def test_is_capture_true():
    state = _make_state((2, 2), (2, 2))
    assert is_capture(state)


def test_is_capture_false():
    state = _make_state((0, 0), (4, 4))
    assert not is_capture(state)


def test_is_timeout_at_max():
    cfg = load_config("config.yaml")
    state = _make_state((0, 0), (4, 4), moves_used=25)
    assert is_timeout(state, cfg)


def test_is_timeout_not_yet():
    cfg = load_config("config.yaml")
    state = _make_state((0, 0), (4, 4), moves_used=24)
    assert not is_timeout(state, cfg)


def test_score_cop_win():
    cfg = load_config("config.yaml")
    assert score_sub_game("COP", cfg) == (20, 5)


def test_score_thief_win():
    cfg = load_config("config.yaml")
    assert score_sub_game("THIEF", cfg) == (5, 10)
