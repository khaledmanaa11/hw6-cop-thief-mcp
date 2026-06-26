from src.game.movers import Mover, GreedyMover, RandomMover


def build_mover(role: str, config) -> Mover:
    name = config.strategy[role]
    if name == "greedy":
        return GreedyMover()
    if name == "random":
        return RandomMover()
    if name == "minimax":
        from src.strategy.minimax import MinimaxMover
        mm = config.strategy["minimax"]
        return MinimaxMover(depth=mm["depth"], weights=mm["weights"], max_moves=config.max_moves)
    if name == "qtable":
        from src.strategy.qtable import QTableMover
        return QTableMover(table_path=config.strategy["qtable"]["path"])
    raise ValueError(f"Unknown mover name: {name!r}. Choose from: greedy, random, minimax, qtable")
