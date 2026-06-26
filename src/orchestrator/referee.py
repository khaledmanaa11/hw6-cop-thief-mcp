from datetime import datetime, timezone

from src.game.config import Config
from src.game.engine import SubGameResult, SeriesResult
from src.game.moves import apply_move, legal_moves
from src.game.rules import is_capture, is_timeout, score_sub_game
from src.game.state import initial_state
from src.orchestrator.recorders import ReplayLog, observe, render_board


def _envelope(side: str, turn: int, move_name: str) -> dict:
    return {
        "from": side,
        "turn": turn,
        "ts": datetime.now(timezone.utc).isoformat(),
        "text": f"{side} plays {move_name}",
    }


async def run_sub_game(
    config: Config,
    cop_gateway,
    thief_gateway,
    cop_mover,
    thief_mover,
    *,
    transcript: list | None = None,
    replay_log: ReplayLog | None = None,
    print_output: bool = False,
) -> SubGameResult:
    state = initial_state(config)
    last_msgs: dict[str, str | None] = {"COP": None, "THIEF": None}

    while True:
        if is_capture(state):
            winner = "COP"
            break
        if is_timeout(state, config):
            winner = "THIEF"
            break

        moves = legal_moves(state)
        if not moves:
            # Pass the turn — no legal moves for this side
            other = "THIEF" if state.to_move == "COP" else "COP"
            from src.game.state import GameState
            state = GameState(
                cop_pos=state.cop_pos,
                thief_pos=state.thief_pos,
                to_move=other,
                moves_used=state.moves_used + 1,
                cop_barriers_left=state.cop_barriers_left,
                board=state.board,
            )
            continue

        side = state.to_move
        gateway = cop_gateway if side == "COP" else thief_gateway
        mover = cop_mover if side == "COP" else thief_mover

        move = mover.choose_move(state)

        # Validate-before-apply: every ply goes through the side's server first
        verdict = await gateway.validate_move(
            to_move=side,
            cop_pos=state.cop_pos,
            thief_pos=state.thief_pos,
            cop_barriers_left=state.cop_barriers_left,
            barriers=list(state.board.barriers),
            move=move.name,
        )
        if not verdict["ok"]:
            raise RuntimeError(
                f"Server rejected legal move {move.name} for {side}: {verdict['reason']}"
            )

        state = apply_move(state, move)

        # Message bus: moving side emits a free-text envelope; other side receives it
        env = _envelope(side, state.moves_used, move.name)
        await gateway.send_message(env)
        other = "THIEF" if side == "COP" else "COP"
        last_msgs[other] = env["text"]

        cop_obs = observe(state, "COP", last_msgs["COP"])
        thief_obs = observe(state, "THIEF", last_msgs["THIEF"])

        record = {
            "turn": state.moves_used,
            "side": side,
            "move": move.name,
            "verdict": verdict,
            "message": env,
            "obs": {"COP": cop_obs, "THIEF": thief_obs},
            "ground_truth": {
                "cop_pos": list(state.cop_pos),
                "thief_pos": list(state.thief_pos),
                "barriers": [list(b) for b in state.board.barriers],
                "moves_used": state.moves_used,
            },
        }

        if transcript is not None:
            transcript.append(record)
        if replay_log is not None:
            replay_log.write(record)
        if print_output:
            print(render_board(state))
            print(f"  Turn {state.moves_used}: {side} plays {move.name} | {env['text']}")

    cop_score, thief_score = score_sub_game(winner, config)
    return SubGameResult(winner, cop_score, thief_score, state.moves_used)


async def run_series(
    config: Config,
    cop_gateway,
    thief_gateway,
    group_a,
    group_b,
    *,
    transcript: list | None = None,
    replay_log: ReplayLog | None = None,
    print_output: bool = False,
) -> SeriesResult:
    sub_games = []
    group_a_total = 0
    group_b_total = 0

    for i in range(config.num_games):
        a_is_cop = (i % 2 == 0)
        cop_mover = group_a if a_is_cop else group_b
        thief_mover = group_b if a_is_cop else group_a

        if print_output:
            print(f"\n--- Sub-game {i + 1}: {'A=Cop B=Thief' if a_is_cop else 'A=Thief B=Cop'} ---")

        result = await run_sub_game(
            config, cop_gateway, thief_gateway, cop_mover, thief_mover,
            transcript=transcript, replay_log=replay_log, print_output=print_output,
        )
        result.cop_group = "A" if a_is_cop else "B"
        result.thief_group = "B" if a_is_cop else "A"
        sub_games.append(result)

        if a_is_cop:
            group_a_total += result.cop_score
            group_b_total += result.thief_score
        else:
            group_a_total += result.thief_score
            group_b_total += result.cop_score

    return SeriesResult(sub_games=sub_games, group_a_total=group_a_total, group_b_total=group_b_total)
