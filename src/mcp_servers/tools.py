from src.game.board import Board
from src.game.state import GameState
from src.game.moves import Move, legal_moves


def _board_with_barriers(config, barriers) -> Board:
    rows, cols = config.grid_size
    board = Board(rows, cols)
    for b in barriers:
        board.barriers.add(tuple(b))
    return board


def ping_result(server_name: str) -> dict:
    return {"ok": True, "server": server_name, "reason": f"{server_name} server alive"}


def validate_location_result(pos, barriers, config) -> dict:
    pos = tuple(pos)
    board = _board_with_barriers(config, barriers)
    if not board.in_bounds(pos):
        return {"ok": False, "reason": f"off-board: {pos} outside grid {config.grid_size}"}
    if board.is_blocked(pos):
        return {"ok": False, "reason": f"blocked: barrier at {pos}"}
    return {"ok": True, "reason": f"clear: {pos} is on-board and unblocked"}


def validate_move_result(to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move, config) -> dict:
    board = _board_with_barriers(config, barriers)
    state = GameState(
        cop_pos=tuple(cop_pos),
        thief_pos=tuple(thief_pos),
        to_move=to_move,
        moves_used=0,
        cop_barriers_left=cop_barriers_left,
        board=board,
    )
    try:
        mv = Move[move]
    except KeyError:
        return {"ok": False, "reason": f"unknown move '{move}'"}
    if mv in legal_moves(state):
        return {"ok": True, "reason": f"legal: {move} for {to_move}"}
    return {"ok": False, "reason": f"illegal: {move} for {to_move} (off-board, blocked, or not allowed)"}


def send_message_result(envelope) -> dict:
    required = ("from", "turn", "ts", "text")
    missing = [k for k in required if k not in envelope]
    if missing:
        return {"ok": False, "reason": f"missing fields: {missing}"}
    if not isinstance(envelope["text"], str):
        return {"ok": False, "reason": "text must be a string"}
    return {"ok": True, "reason": f"message accepted from {envelope['from']} at turn {envelope['turn']}"}


def place_barrier_result(pos, cop_barriers_left, barriers, config) -> dict:
    pos = tuple(pos)
    board = _board_with_barriers(config, barriers)
    if cop_barriers_left <= 0:
        return {"ok": False, "reason": "no barriers left"}
    if not board.in_bounds(pos):
        return {"ok": False, "reason": f"off-board: {pos} outside grid {config.grid_size}"}
    if board.is_blocked(pos):
        return {"ok": False, "reason": f"barrier already at {pos}"}
    return {"ok": True, "reason": f"valid barrier site: {pos}"}
