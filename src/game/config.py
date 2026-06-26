from dataclasses import dataclass
import yaml


@dataclass
class ScoringConfig:
    cop_win: int
    thief_win: int
    cop_loss: int
    thief_loss: int


@dataclass
class ServerEndpoint:
    host: str
    port: int


@dataclass
class ServersConfig:
    cop: ServerEndpoint
    thief: ServerEndpoint


_DEFAULT_STRATEGY = {
    "cop": "minimax",
    "thief": "minimax",
    "minimax": {
        "depth": 4,
        "weights": {
            "dist": 1.0,
            "thief_mob": 0.3,
            "corner": 0.2,
            "reach": 0.15,
            "capture": 1000.0,
        },
    },
    "qtable": {
        "path": "models/qtable.json",
        "train": {"episodes": 20000, "alpha": 0.3, "gamma": 0.95, "epsilon": 0.2, "seed": 7},
    },
}


@dataclass
class Config:
    grid_size: tuple[int, int]
    max_moves: int
    num_games: int
    max_barriers: int
    scoring: ScoringConfig
    servers: ServersConfig | None = None
    output_run_dir: str = "runs"
    strategy: dict | None = None


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

    servers = None
    if "servers" in data:
        sv = data["servers"]

        def _endpoint(d):
            host = d["host"]
            port = d["port"]
            if not host:
                raise ValueError("server host must be non-empty")
            if not (1 <= port <= 65535):
                raise ValueError(f"server port out of range: {port}")
            return ServerEndpoint(host=host, port=port)

        servers = ServersConfig(cop=_endpoint(sv["cop"]), thief=_endpoint(sv["thief"]))

    output_run_dir = "runs"
    if "output" in data and "run_dir" in data["output"]:
        run_dir = data["output"]["run_dir"]
        if not run_dir:
            raise ValueError("output.run_dir must be non-empty")
        output_run_dir = run_dir

    strategy = dict(_DEFAULT_STRATEGY)
    if "strategy" in data:
        strategy.update(data["strategy"])

    return Config(
        grid_size=(gs[0], gs[1]),
        max_moves=max_moves,
        num_games=num_games,
        max_barriers=max_barriers,
        scoring=scoring,
        servers=servers,
        output_run_dir=output_run_dir,
        strategy=strategy,
    )
