import pytest
from src.game.board import Board
from src.game.state import GameState
from src.game.config import load_config
from src.strategy.evaluate import evaluate


@pytest.fixture
def cfg():
    return load_config("config.yaml")


def _state(cop, thief, board, moves_used=0, barriers_left=5):
    return GameState(
        cop_pos=cop,
        thief_pos=thief,
        to_move="COP",
        moves_used=moves_used,
        cop_barriers_left=barriers_left,
        board=board,
    )


def test_evaluate_prefers_capture(cfg):
    board = Board(5, 5)
    captured = _state((2, 2), (2, 2), board)
    far = _state((0, 0), (4, 4), board)
    assert evaluate(captured, cfg) > evaluate(far, cfg)


def test_evaluate_closer_is_better(cfg):
    board = Board(5, 5)
    close = _state((1, 1), (2, 2), board)
    far = _state((0, 0), (4, 4), board)
    assert evaluate(close, cfg) > evaluate(far, cfg)


def test_evaluate_timeout_negative(cfg):
    board = Board(5, 5)
    timed = _state((0, 0), (4, 4), board, moves_used=cfg.max_moves)
    non_terminal = _state((0, 0), (4, 4), board, moves_used=0)
    assert evaluate(timed, cfg) < evaluate(non_terminal, cfg)
