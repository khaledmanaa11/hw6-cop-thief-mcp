from enum import Enum
import dataclasses
from src.game.state import GameState


class Move(Enum):
    N = (-1, 0)
    S = (1, 0)
    E = (0, 1)
    W = (0, -1)
    NE = (-1, 1)
    NW = (-1, -1)
    SE = (1, 1)
    SW = (1, -1)
    PLACE_BARRIER = None


def _target(pos: tuple[int, int], move: Move) -> tuple[int, int]:
    r, c = pos
    dr, dc = move.value
    return (r + dr, c + dc)


def legal_moves(state: GameState) -> list[Move]:
    board = state.board
    if state.to_move == "THIEF":
        pos = state.thief_pos
    else:
        pos = state.cop_pos

    result = []
    for move in Move:
        if move is Move.PLACE_BARRIER:
            continue
        target = _target(pos, move)
        if board.in_bounds(target) and not board.is_blocked(target):
            result.append(move)

    if (
        state.to_move == "COP"
        and state.cop_barriers_left > 0
        and not board.is_blocked(state.cop_pos)
    ):
        result.append(Move.PLACE_BARRIER)

    return result


def apply_move(state: GameState, move: Move) -> GameState:
    if move not in legal_moves(state):
        raise ValueError(f"Move {move} is not legal in the current state")

    board = state.board
    cop_pos = state.cop_pos
    thief_pos = state.thief_pos
    cop_barriers_left = state.cop_barriers_left

    if move is Move.PLACE_BARRIER:
        board.place_barrier(cop_pos)
        cop_barriers_left -= 1
    else:
        if state.to_move == "THIEF":
            thief_pos = _target(thief_pos, move)
        else:
            cop_pos = _target(cop_pos, move)

    next_to_move = "COP" if state.to_move == "THIEF" else "THIEF"

    return GameState(
        cop_pos=cop_pos,
        thief_pos=thief_pos,
        to_move=next_to_move,
        moves_used=state.moves_used + 1,
        cop_barriers_left=cop_barriers_left,
        board=board,
    )
