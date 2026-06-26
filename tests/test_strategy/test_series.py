from src.game.config import load_config
from src.game.engine import play_series
from src.strategy.factory import build_mover


def test_series_with_minimax_band():
    cfg = load_config("config.yaml")
    cop = build_mover("cop", cfg)
    thief = build_mover("thief", cfg)
    result = play_series(cfg, cop, thief)
    assert 30 <= result.group_a_total <= 90
    assert 30 <= result.group_b_total <= 90
