from dataclasses import dataclass
from src.game.board import Board


@dataclass
class GameState:
    cop_pos: tuple[int, int]
    thief_pos: tuple[int, int]
    to_move: str
    moves_used: int
    cop_barriers_left: int
    board: Board


def initial_state(config) -> GameState:
    rows, cols = config.grid_size
    board = Board(rows, cols)
    return GameState(
        cop_pos=(0, 0),
        thief_pos=(rows - 1, cols - 1),
        to_move="THIEF",
        moves_used=0,
        cop_barriers_left=config.max_barriers,
        board=board,
    )
