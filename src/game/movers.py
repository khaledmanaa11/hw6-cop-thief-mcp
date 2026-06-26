import random
from typing import Protocol
from src.game.state import GameState
from src.game.moves import Move, legal_moves


class Mover(Protocol):
    def choose_move(self, state: GameState) -> Move: ...


class RandomMover:
    def choose_move(self, state: GameState) -> Move:
        return random.choice(legal_moves(state))


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class GreedyMover:
    """Deterministic Chebyshev pursue/evade mover.

    Moves are 8-directional king moves, so Chebyshev distance equals the minimum
    number of moves and is the correct greedy metric. The Cop minimizes distance to
    the Thief; the Thief maximizes distance from the Cop. Never proposes
    PLACE_BARRIER (barrier strategy is Step 4). Ties are broken by Move declaration
    order — legal_moves yields candidates in enum order and the first best is kept,
    so the choice is fully reproducible (no RNG).
    """

    def choose_move(self, state: GameState) -> Move:
        candidates = [m for m in legal_moves(state) if m is not Move.PLACE_BARRIER]

        if state.to_move == "COP":
            origin, target = state.cop_pos, state.thief_pos
            best_key = min
        else:
            origin, target = state.thief_pos, state.cop_pos
            best_key = max

        def distance_after(move: Move) -> int:
            dr, dc = move.value
            moved = (origin[0] + dr, origin[1] + dc)
            return _chebyshev(moved, target)

        return best_key(candidates, key=distance_after)
