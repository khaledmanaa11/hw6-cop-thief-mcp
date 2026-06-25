from dataclasses import dataclass
from src.game.state import initial_state, GameState
from src.game.moves import legal_moves, apply_move
from src.game.rules import is_capture, is_timeout, score_sub_game


@dataclass
class SubGameResult:
    winner: str
    cop_score: int
    thief_score: int
    moves_used: int


@dataclass
class SeriesResult:
    sub_games: list[SubGameResult]
    cop_total: int
    thief_total: int


def play_sub_game(config, cop_mover, thief_mover) -> SubGameResult:
    state = initial_state(config)

    while True:
        if is_capture(state):
            winner = "COP"
            break
        if is_timeout(state, config):
            winner = "THIEF"
            break

        moves = legal_moves(state)
        if not moves:
            next_to_move = "COP" if state.to_move == "THIEF" else "THIEF"
            state = GameState(
                cop_pos=state.cop_pos,
                thief_pos=state.thief_pos,
                to_move=next_to_move,
                moves_used=state.moves_used + 1,
                cop_barriers_left=state.cop_barriers_left,
                board=state.board,
            )
            continue

        mover = thief_mover if state.to_move == "THIEF" else cop_mover
        move = mover.choose_move(state)
        state = apply_move(state, move)

    cop_score, thief_score = score_sub_game(winner, config)
    return SubGameResult(winner, cop_score, thief_score, state.moves_used)


def play_series(config, cop_mover, thief_mover) -> SeriesResult:
    sub_games = []
    cop_total = 0
    thief_total = 0

    for _ in range(config.num_games):
        result = play_sub_game(config, cop_mover, thief_mover)
        sub_games.append(result)
        cop_total += result.cop_score
        thief_total += result.thief_score

    return SeriesResult(sub_games=sub_games, cop_total=cop_total, thief_total=thief_total)
