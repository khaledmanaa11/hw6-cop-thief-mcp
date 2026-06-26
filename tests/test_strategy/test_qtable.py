import json
import pytest
from src.game.board import Board
from src.game.state import GameState
from src.game.moves import legal_moves
from src.strategy.qtable import QTableMover


def _state(cop, thief, barriers_left=5):
    board = Board(3, 3)
    return GameState(
        cop_pos=cop, thief_pos=thief, to_move="COP",
        moves_used=0, cop_barriers_left=barriers_left, board=board,
    )


@pytest.fixture
def tmp_table(tmp_path):
    table = {
        "-1,-1,COP,1": {"N": 5.0, "S": 1.0, "SE": 3.0},
        "0,0,COP,1": {"NE": 2.0},
    }
    p = tmp_path / "q.json"
    p.write_text(json.dumps(table))
    return str(p)


def test_qtable_loads_and_plays(tmp_table):
    mover = QTableMover(tmp_table)
    board = Board(3, 3)
    for cop in [(0, 0), (1, 1), (2, 2)]:
        for thief in [(r, c) for r in range(3) for c in range(3) if (r, c) != cop]:
            state = GameState(
                cop_pos=cop, thief_pos=thief, to_move="COP",
                moves_used=0, cop_barriers_left=5, board=board,
            )
            move = mover.choose_move(state)
            assert move in legal_moves(state)


def test_qtable_argmax_deterministic(tmp_table):
    mover = QTableMover(tmp_table)
    state = _state((2, 2), (1, 1))
    move1 = mover.choose_move(state)
    move2 = mover.choose_move(state)
    assert move1 == move2


def test_qtable_picks_best_from_table(tmp_table):
    mover = QTableMover(tmp_table)
    state = _state((2, 2), (1, 1))
    move = mover.choose_move(state)
    legal = legal_moves(state)
    assert move in legal


def test_qtable_fallback_on_unseen(tmp_table):
    mover = QTableMover(tmp_table)
    board = Board(5, 5)
    state = GameState(
        cop_pos=(2, 2), thief_pos=(2, 4), to_move="THIEF",
        moves_used=0, cop_barriers_left=0, board=board,
    )
    move = mover.choose_move(state)
    assert move in legal_moves(state)
