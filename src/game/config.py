from dataclasses import dataclass
import yaml


@dataclass
class ScoringConfig:
    cop_win: int
    thief_win: int
    cop_loss: int
    thief_loss: int


@dataclass
class Config:
    grid_size: tuple[int, int]
    max_moves: int
    num_games: int
    max_barriers: int
    scoring: ScoringConfig


def load_config(path: str) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)

    gs = data["grid_size"]
    if len(gs) != 2 or gs[0] <= 0 or gs[1] <= 0:
        raise ValueError(f"Invalid grid_size: {gs}")

    max_moves = data["max_moves"]
    if max_moves <= 0:
        raise ValueError(f"max_moves must be > 0, got {max_moves}")

    num_games = data["num_games"]
    if num_games <= 0:
        raise ValueError(f"num_games must be > 0, got {num_games}")

    max_barriers = data["max_barriers"]
    if max_barriers < 0:
        raise ValueError(f"max_barriers must be >= 0, got {max_barriers}")

    s = data["scoring"]
    for key in ("cop_win", "thief_win", "cop_loss", "thief_loss"):
        if s[key] < 0:
            raise ValueError(f"scoring.{key} must be >= 0")

    scoring = ScoringConfig(
        cop_win=s["cop_win"],
        thief_win=s["thief_win"],
        cop_loss=s["cop_loss"],
        thief_loss=s["thief_loss"],
    )

    return Config(
        grid_size=(gs[0], gs[1]),
        max_moves=max_moves,
        num_games=num_games,
        max_barriers=max_barriers,
        scoring=scoring,
    )
