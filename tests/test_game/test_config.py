import pytest
from src.game.config import load_config


def test_load_config_types():
    cfg = load_config("config.yaml")
    assert cfg.grid_size == (5, 5)
    assert cfg.max_moves == 25
    assert cfg.num_games == 6
    assert cfg.max_barriers == 5
    assert cfg.scoring.cop_win == 20
    assert cfg.scoring.thief_win == 10
    assert cfg.scoring.cop_loss == 5
    assert cfg.scoring.thief_loss == 5


def test_invalid_grid_raises(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("grid_size: [0, 5]\nmax_moves: 25\nnum_games: 6\nmax_barriers: 5\nscoring:\n  cop_win: 20\n  thief_win: 10\n  cop_loss: 5\n  thief_loss: 5\n")
    with pytest.raises(ValueError):
        load_config(str(bad_yaml))
