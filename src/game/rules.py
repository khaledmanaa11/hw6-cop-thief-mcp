from src.game.state import GameState


def is_capture(state: GameState) -> bool:
    return state.cop_pos == state.thief_pos


def is_timeout(state: GameState, config) -> bool:
    return state.moves_used >= config.max_moves


def score_sub_game(winner: str, config) -> tuple[int, int]:
    if winner == "COP":
        return (config.scoring.cop_win, config.scoring.thief_loss)
    return (config.scoring.cop_loss, config.scoring.thief_win)
