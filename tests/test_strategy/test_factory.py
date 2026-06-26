import pytest
from src.game.config import load_config
from src.game.movers import GreedyMover, RandomMover
from src.strategy.factory import build_mover


@pytest.fixture
def cfg():
    return load_config("config.yaml")


def test_build_mover_types(cfg):
    original = cfg.strategy["cop"]

    cfg.strategy["cop"] = "greedy"
    assert isinstance(build_mover("cop", cfg), GreedyMover)

    cfg.strategy["cop"] = "random"
    assert isinstance(build_mover("cop", cfg), RandomMover)

    cfg.strategy["cop"] = original


def test_build_mover_minimax(cfg):
    from src.strategy.minimax import MinimaxMover
    cfg.strategy["cop"] = "minimax"
    m = build_mover("cop", cfg)
    assert isinstance(m, MinimaxMover)


def test_build_mover_qtable(cfg):
    from src.strategy.qtable import QTableMover
    cfg.strategy["cop"] = "qtable"
    m = build_mover("cop", cfg)
    assert isinstance(m, QTableMover)


def test_build_mover_unknown_raises(cfg):
    cfg.strategy["cop"] = "nonexistent"
    with pytest.raises(ValueError, match="Unknown mover"):
        build_mover("cop", cfg)
