from src.game.board import Board
from src.game.state import GameState
from src.game.moves import Move, legal_moves, apply_move
from src.game.rules import is_capture, is_timeout
from src.strategy.evaluate import evaluate


def _clone(state: GameState) -> GameState:
    new_board = Board(state.board.rows, state.board.cols)
    new_board.barriers = set(state.board.barriers)
    return GameState(
        cop_pos=state.cop_pos,
        thief_pos=state.thief_pos,
        to_move=state.to_move,
        moves_used=state.moves_used,
        cop_barriers_left=state.cop_barriers_left,
        board=new_board,
    )


class _SearchConfig:
    """Minimal config proxy forwarded into evaluate/is_timeout during search."""
    def __init__(self, weights: dict, max_moves: int) -> None:
        self._weights = weights
        self.max_moves = max_moves

    @property
    def strategy(self):
        return {"minimax": {"weights": self._weights}}


class MinimaxMover:
    def __init__(self, depth: int, weights: dict, max_moves: int = 0) -> None:
        self._depth = depth
        self._weights = weights
        self._max_moves = max_moves  # set by factory from config; 0 means no timeout in search

    def choose_move(self, state: GameState) -> Move:
        cfg = _SearchConfig(self._weights, self._max_moves)
        is_max = state.to_move == "COP"
        best_val = float("-inf") if is_max else float("inf")
        best_move = None

        for move in legal_moves(state):
            child = apply_move(_clone(state), move)
            val = self._search(child, self._depth - 1, float("-inf"), float("inf"), cfg)
            if is_max:
                if best_move is None or val > best_val:
                    best_val = val
                    best_move = move
            else:
                if best_move is None or val < best_val:
                    best_val = val
                    best_move = move

        return best_move

    def _search(self, state: GameState, depth: int, alpha: float, beta: float, cfg) -> float:
        if is_capture(state):
            return evaluate(state, cfg)
        if self._max_moves > 0 and is_timeout(state, cfg):
            return evaluate(state, cfg)
        if depth == 0:
            return evaluate(state, cfg)

        moves = legal_moves(state)
        if not moves:
            skip = GameState(
                cop_pos=state.cop_pos,
                thief_pos=state.thief_pos,
                to_move="COP" if state.to_move == "THIEF" else "THIEF",
                moves_used=state.moves_used + 1,
                cop_barriers_left=state.cop_barriers_left,
                board=state.board,
            )
            return self._search(skip, depth - 1, alpha, beta, cfg)

        if state.to_move == "COP":
            val = float("-inf")
            for move in moves:
                child = apply_move(_clone(state), move)
                val = max(val, self._search(child, depth - 1, alpha, beta, cfg))
                alpha = max(alpha, val)
                if alpha >= beta:
                    break
            return val
        else:
            val = float("inf")
            for move in moves:
                child = apply_move(_clone(state), move)
                val = min(val, self._search(child, depth - 1, alpha, beta, cfg))
                beta = min(beta, val)
                if alpha >= beta:
                    break
            return val
