import dataclasses
import pytest
from src.game.config import Config, ScoringConfig
from src.game.engine import play_series
from src.strategy.factory import build_mover


_SCORING = ScoringConfig(cop_win=20, thief_win=10, cop_loss=5, thief_loss=5)


def _cfg(size: int, mover_name: str) -> Config:
    return Config(
        grid_size=(size, size), max_moves=25, num_games=2, max_barriers=2,
        scoring=_SCORING,
        strategy={
            "cop": mover_name, "thief": mover_name,
            "minimax": {"depth": 2, "weights": {
                "dist": 1.0, "thief_mob": 0.3, "corner": 0.2, "reach": 0.15, "capture": 1000.0,
            }},
            "qtable": {"path": "models/qtable.json", "train": {}},
        },
    )


@pytest.mark.parametrize("size", [2, 3, 4, 5])
@pytest.mark.parametrize("name", ["minimax", "qtable", "greedy"])
def test_brains_resizable_ladder(size, name):
    cfg = _cfg(size, name)
    cop = build_mover("cop", cfg)
    thief = build_mover("thief", cfg)
    result = play_series(cfg, cop, thief)
    total = result.group_a_total + result.group_b_total
    assert total > 0
