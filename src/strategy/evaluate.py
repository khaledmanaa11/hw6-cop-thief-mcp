from collections import deque
from src.game.state import GameState
from src.game.rules import is_capture, is_timeout


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _open_neighbours(pos: tuple[int, int], board) -> int:
    count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nb = (pos[0] + dr, pos[1] + dc)
            if board.in_bounds(nb) and not board.is_blocked(nb):
                count += 1
    return count


def _corner_pressure(pos: tuple[int, int], board) -> float:
    r, c = pos
    rows, cols = board.rows, board.cols
    dist_to_edge = min(r, rows - 1 - r, c, cols - 1 - c)
    return 1.0 / (dist_to_edge + 1)


def _reachable_area(pos: tuple[int, int], board, budget: int) -> int:
    visited = {pos}
    frontier = deque([(pos, 0)])
    while frontier:
        cur, depth = frontier.popleft()
        if depth >= budget:
            continue
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nb = (cur[0] + dr, cur[1] + dc)
                if nb not in visited and board.in_bounds(nb) and not board.is_blocked(nb):
                    visited.add(nb)
                    frontier.append((nb, depth + 1))
    return len(visited)


def evaluate(state: GameState, config) -> float:
    w = config.strategy["minimax"]["weights"]
    w_dist = w["dist"]
    w_mob = w["thief_mob"]
    w_corner = w["corner"]
    w_reach = w["reach"]
    w_cap = w["capture"]

    if is_capture(state):
        return w_cap - state.moves_used

    max_moves = config.max_moves
    if state.moves_used >= max_moves:
        return -w_cap + state.moves_used

    dist = _chebyshev(state.cop_pos, state.thief_pos)
    mob = _open_neighbours(state.thief_pos, state.board)
    corner = _corner_pressure(state.thief_pos, state.board)
    budget = max(1, max_moves - state.moves_used)
    reach = _reachable_area(state.thief_pos, state.board, budget)

    return -w_dist * dist - w_mob * mob + w_corner * corner - w_reach * reach
