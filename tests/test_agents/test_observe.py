from src.game.board import Board
from src.game.state import GameState
from src.orchestrator.recorders import observe


def _state(cop=(0, 0), thief=(2, 2), rows=3, cols=3):
    return GameState(cop, thief, "COP", 1, 2, Board(rows, cols))


def test_blind_observation_hides_opponent():
    view = observe(
        _state(),
        "COP",
        mode="blind",
        params={"max_moves": 8},
        inbox=[],
    )

    assert view["sees_opponent"] is False
    assert view["opponent_pos"] is None
    assert view["opponent_hint"] == "unseen"


def test_noisy_reveals_inside_radius():
    view = observe(
        _state(cop=(1, 1), thief=(2, 2)),
        "COP",
        mode="noisy",
        params={"max_moves": 8, "noisy": {"reveal_radius": 1, "quadrant_hint": True}},
        inbox=[],
    )

    assert view["sees_opponent"] is True
    assert view["opponent_pos"] == [2, 2]
    assert view["opponent_hint"] == "exact"


def test_noisy_uses_coarse_hint_outside_radius():
    view = observe(
        _state(),
        "COP",
        mode="noisy",
        params={"max_moves": 8, "noisy": {"reveal_radius": 1, "quadrant_hint": True}},
        inbox=[],
    )

    assert view["sees_opponent"] is False
    assert view["opponent_pos"] is None
    assert view["opponent_hint"] == "southeast"


def test_full_observation_preserves_step3_truth():
    view = observe(
        _state(),
        "COP",
        mode="full",
        params={"max_moves": 8},
        inbox=[],
    )

    assert view["sees_opponent"] is True
    assert view["opponent_pos"] == [2, 2]


def test_observe_old_signature_still_full_visibility():
    view = observe(_state(), "COP", "THIEF plays N")

    assert set(view.keys()) == {"self", "sees_opponent", "opponent_pos", "last_msg", "barriers"}
    assert view["sees_opponent"] is True
    assert view["opponent_pos"] == [2, 2]
    assert view["last_msg"] == "THIEF plays N"
