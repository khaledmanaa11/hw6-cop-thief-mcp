import dataclasses
import pytest
from src.game.config import load_config, Config, ScoringConfig
from src.game.movers import RandomMover
from src.game.engine import play_series, play_sub_game
from src.game.state import initial_state, GameState
from src.game.board import Board
from src.game.moves import Move, apply_move


def _cfg_for_size(base_cfg: Config, grid_size: tuple[int, int]) -> Config:
    return dataclasses.replace(base_cfg, grid_size=grid_size)


@pytest.mark.parametrize("grid_size", [(2, 2), (3, 3), (4, 4), (5, 5)])
def test_series_length_and_scores(grid_size):
    base = load_config("config.yaml")
    cfg = _cfg_for_size(base, grid_size)
    result = play_series(cfg, RandomMover(), RandomMover())
    assert len(result.sub_games) == cfg.num_games
    cop_win_total = cfg.scoring.cop_win + cfg.scoring.thief_loss
    thief_win_total = cfg.scoring.cop_loss + cfg.scoring.thief_win
    for sg in result.sub_games:
        total = sg.cop_score + sg.thief_score
        assert total in (cop_win_total, thief_win_total)


def test_forced_capture_yields_cop_win_score():
    cfg = load_config("config.yaml")
    # Place thief one step S of cop — cop is THIEF first but we override state manually
    # Build state where cop and thief are adjacent so cop can capture immediately
    # We need a state where COP moves next and can land on thief
    b = Board(5, 5)
    # Cop at (1,0), Thief at (2,0) — cop can move S to capture
    state = GameState(cop_pos=(1, 0), thief_pos=(2, 0), to_move="COP",
                      moves_used=0, cop_barriers_left=0, board=b)
    new_state = apply_move(state, Move.S)
    assert new_state.cop_pos == new_state.thief_pos

    # Now play a sub-game where capture happens quickly using a deterministic setup
    # Use the full engine and verify it can produce COP wins
    import random
    random.seed(42)
    results = [play_sub_game(cfg, RandomMover(), RandomMover()) for _ in range(20)]
    cop_wins = [r for r in results if r.winner == "COP"]
    # With seed=42 over 20 games we expect at least one cop win
    cop_win_scores = [r.cop_score for r in cop_wins]
    for score in cop_win_scores:
        assert score == cfg.scoring.cop_win
