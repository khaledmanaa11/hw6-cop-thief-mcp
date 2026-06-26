from src.game.config import load_config
from src.game.movers import RandomMover
from src.game.engine import play_series


def main() -> None:
    config = load_config("config.yaml")
    result = play_series(config, RandomMover(), RandomMover())

    for i, sg in enumerate(result.sub_games, 1):
        winning_group = sg.cop_group if sg.winner == "COP" else sg.thief_group
        print(
            f"Sub-game {i}: Cop=Group {sg.cop_group}  Thief=Group {sg.thief_group}  "
            f"-> {sg.winner} wins (Group {winning_group})  moves={sg.moves_used}"
        )

    print(f"Series totals: Group A={result.group_a_total}  Group B={result.group_b_total}")


if __name__ == "__main__":
    main()
