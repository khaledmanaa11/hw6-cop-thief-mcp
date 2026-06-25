import pytest
from src.game.board import Board
from src.game.state import GameState
from src.game.moves import legal_moves


def test_in_bounds():
    b = Board(5, 5)
    assert b.in_bounds((0, 0))
    assert b.in_bounds((4, 4))
    assert not b.in_bounds((5, 0))
    assert not b.in_bounds((0, -1))


def test_is_blocked():
    b = Board(5, 5)
    assert not b.is_blocked((2, 2))
    b.place_barrier((2, 2))
    assert b.is_blocked((2, 2))


def test_place_barrier_duplicate_raises():
    b = Board(5, 5)
    b.place_barrier((1, 1))
    with pytest.raises(ValueError):
        b.place_barrier((1, 1))


def test_place_barrier_out_of_bounds_raises():
    b = Board(5, 5)
    with pytest.raises(ValueError):
        b.place_barrier((9, 9))


def test_barrier_blocks_legal_moves():
    b = Board(5, 5)
    b.place_barrier((1, 0))
    # Thief at (2,0), cop far away; move N would go to (1,0) which is blocked
    state = GameState(cop_pos=(4, 4), thief_pos=(2, 0), to_move="THIEF", moves_used=0, cop_barriers_left=0, board=b)
    moves = legal_moves(state)
    from src.game.moves import Move
    assert Move.N not in moves

    # Cop also cannot move to a barrier cell
    state2 = GameState(cop_pos=(2, 0), thief_pos=(4, 4), to_move="COP", moves_used=0, cop_barriers_left=0, board=b)
    moves2 = legal_moves(state2)
    assert Move.N not in moves2
