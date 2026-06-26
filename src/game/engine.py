from dataclasses import dataclass
from src.game.state import initial_state, GameState
from src.game.moves import legal_moves, apply_move
from src.game.rules import is_capture, is_timeout, score_sub_game


@dataclass
class SubGameResult:
    winner: str            # "COP" or "THIEF" — which ROLE won this sub-game
    cop_score: int
    thief_score: int
    moves_used: int
    cop_group: str = ""    # which GROUP ("A"/"B") played Cop this sub-game
    thief_group: str = ""  # which GROUP ("A"/"B") played Thief this sub-game


@dataclass
class SeriesResult:
    sub_games: list[SubGameResult]
    group_a_total: int     # group A's score = its Cop points + its Thief points
    group_b_total: int     # group B's score = its Cop points + its Thief points


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


def play_series(config, group_a, group_b) -> SeriesResult:
    """Run num_games sub-games between two GROUPS, swapping roles each sub-game.

    Per the assignment (§4.4), each group plays as Cop in half the sub-games and as
    Thief in the other half; its series score is its Cop points plus its Thief points.
    With the default 6 sub-games a group is Cop 3× and Thief 3× → max 90, min 30.
    """
    sub_games = []
    group_a_total = 0
    group_b_total = 0

    for i in range(config.num_games):
        # Alternate roles: even sub-games A=Cop/B=Thief, odd sub-games A=Thief/B=Cop.
        a_is_cop = (i % 2 == 0)
        cop_mover = group_a if a_is_cop else group_b
        thief_mover = group_b if a_is_cop else group_a

        result = play_sub_game(config, cop_mover, thief_mover)
        result.cop_group = "A" if a_is_cop else "B"
        result.thief_group = "B" if a_is_cop else "A"
        sub_games.append(result)

        # Attribute each role's points to the group that played that role.
        if a_is_cop:
            group_a_total += result.cop_score
            group_b_total += result.thief_score
        else:
            group_a_total += result.thief_score
            group_b_total += result.cop_score

    return SeriesResult(sub_games=sub_games, group_a_total=group_a_total, group_b_total=group_b_total)
