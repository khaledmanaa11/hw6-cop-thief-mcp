import pytest
from src.game.board import Board
from src.game.state import GameState
from src.game.moves import Move, legal_moves, apply_move


def _state(cop_pos=(0, 0), thief_pos=(4, 4), to_move="THIEF", moves_used=0, cop_barriers_left=5, board=None):
    if board is None:
        board = Board(5, 5)
    return GameState(cop_pos=cop_pos, thief_pos=thief_pos, to_move=to_move,
                     moves_used=moves_used, cop_barriers_left=cop_barriers_left, board=board)


def test_eight_directional_members():
    dirs = {m for m in Move if m is not Move.PLACE_BARRIER}
    assert len(dirs) == 8


def test_out_of_bounds_move_rejected():
    # Thief at corner (0,0) — moves N, W, NW, NE, SW are OOB
    state = _state(thief_pos=(0, 0), cop_pos=(4, 4), to_move="THIEF")
    with pytest.raises(ValueError):
        apply_move(state, Move.N)


def test_barrier_cell_move_rejected():
    b = Board(5, 5)
    b.place_barrier((1, 0))
    state = _state(thief_pos=(2, 0), cop_pos=(4, 4), to_move="THIEF", board=b)
    with pytest.raises(ValueError):
        apply_move(state, Move.N)


def test_thief_never_gets_place_barrier():
    state = _state(to_move="THIEF", cop_barriers_left=5)
    moves = legal_moves(state)
    assert Move.PLACE_BARRIER not in moves


def test_cop_loses_place_barrier_when_none_left():
    state = _state(to_move="COP", cop_barriers_left=0)
    moves = legal_moves(state)
    assert Move.PLACE_BARRIER not in moves


def test_cop_gets_place_barrier_when_available():
    state = _state(to_move="COP", cop_barriers_left=3)
    moves = legal_moves(state)
    assert Move.PLACE_BARRIER in moves


def test_apply_move_increments_moves_used():
    state = _state(to_move="THIEF")
    move = legal_moves(state)[0]
    new_state = apply_move(state, move)
    assert new_state.moves_used == 1


def test_apply_move_flips_to_move():
    state = _state(to_move="THIEF")
    move = legal_moves(state)[0]
    new_state = apply_move(state, move)
    assert new_state.to_move == "COP"
