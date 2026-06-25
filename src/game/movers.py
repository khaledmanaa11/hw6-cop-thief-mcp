import random
from typing import Protocol
from src.game.state import GameState
from src.game.moves import Move, legal_moves


class Mover(Protocol):
    def choose_move(self, state: GameState) -> Move: ...


class RandomMover:
    def choose_move(self, state: GameState) -> Move:
        return random.choice(legal_moves(state))
