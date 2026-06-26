"""Q-table mover using a board-size-agnostic abstract state key.

Key abstraction: "<cdr>,<cdc>,<to_move>,<barriers_bucket>"
  cdr/cdc: sign of (thief_pos - cop_pos) each axis → {-1, 0, 1}
  barriers_bucket: 1 if cop_barriers_left > 0 else 0

Generalises across board sizes. Unseen keys fall back to GreedyMover.
"""
import json
from src.game.moves import Move, legal_moves
from src.game.movers import GreedyMover

_FALLBACK = GreedyMover()


def _key(state) -> str:
    dr = state.thief_pos[0] - state.cop_pos[0]
    dc = state.thief_pos[1] - state.cop_pos[1]
    cdr = 0 if dr == 0 else (1 if dr > 0 else -1)
    cdc = 0 if dc == 0 else (1 if dc > 0 else -1)
    bucket = 1 if state.cop_barriers_left > 0 else 0
    return f"{cdr},{cdc},{state.to_move},{bucket}"


class QTableMover:
    def __init__(self, table_path: str) -> None:
        try:
            with open(table_path) as f:
                self._table: dict[str, dict[str, float]] = json.load(f)
        except FileNotFoundError:
            self._table = {}

    def choose_move(self, state) -> Move:
        key = _key(state)
        legal = legal_moves(state)
        legal_names = {m.name for m in legal}

        if key in self._table:
            q_row = self._table[key]
            best_q: float | None = None
            best_move: Move | None = None
            for m in Move:  # enum declaration order → deterministic tie-break
                if m.name in legal_names and m.name in q_row:
                    if best_q is None or q_row[m.name] > best_q:
                        best_q = q_row[m.name]
                        best_move = m
            if best_move is not None:
                return best_move

        return _FALLBACK.choose_move(state)
