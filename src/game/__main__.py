from src.game.config import load_config
from src.game.movers import RandomMover
from src.game.engine import play_series


def main() -> None:
    config = load_config("config.yaml")
    result = play_series(config, RandomMover(), RandomMover())

    for i, sg in enumerate(result.sub_games, 1):
        print(f"Sub-game {i}: winner={sg.winner} cop={sg.cop_score} thief={sg.thief_score} moves={sg.moves_used}")

    print(f"Series totals: cop={result.cop_total} thief={result.thief_total}")


if __name__ == "__main__":
    main()
