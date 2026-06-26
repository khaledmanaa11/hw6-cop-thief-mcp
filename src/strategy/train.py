"""Offline seeded ε-greedy Q-learning trainer for the Cop & Thief game.

Usage:
    python -m src.strategy.train [--config config.yaml] [--out models/qtable.json]

The trained table is committed so a fresh checkout runs QTableMover with no training.
This module is never imported at runtime.
"""
import json
import random
import argparse
from pathlib import Path

from src.game.config import load_config
from src.game.state import GameState
from src.game.board import Board
from src.game.moves import Move, legal_moves, apply_move
from src.game.rules import is_capture, is_timeout


def _key(state: GameState) -> str:
    dr = state.thief_pos[0] - state.cop_pos[0]
    dc = state.thief_pos[1] - state.cop_pos[1]
    cdr = 0 if dr == 0 else (1 if dr > 0 else -1)
    cdc = 0 if dc == 0 else (1 if dc > 0 else -1)
    bucket = 1 if state.cop_barriers_left > 0 else 0
    return f"{cdr},{cdc},{state.to_move},{bucket}"


def _reward(prev: GameState, next_state: GameState, config, winner: str | None) -> float:
    if winner == "COP":
        return config.scoring.cop_win if next_state.to_move == "THIEF" else -config.scoring.thief_loss
    if winner == "THIEF":
        return -config.scoring.thief_win if prev.to_move == "THIEF" else config.scoring.cop_loss
    return -1.0  # step penalty


def _random_start(rng: random.Random, config) -> GameState:
    rows, cols = config.grid_size
    positions = [(r, c) for r in range(rows) for c in range(cols)]
    cop_pos = rng.choice(positions)
    thief_pos = rng.choice([p for p in positions if p != cop_pos])
    board = Board(rows, cols)
    return GameState(
        cop_pos=cop_pos, thief_pos=thief_pos, to_move="THIEF",
        moves_used=0, cop_barriers_left=config.max_barriers, board=board,
    )


def train(config, out_path: str) -> None:
    train_cfg = config.strategy["qtable"]["train"]
    episodes = train_cfg["episodes"]
    alpha = train_cfg["alpha"]
    gamma = train_cfg["gamma"]
    epsilon = train_cfg["epsilon"]
    seed = train_cfg["seed"]

    rng = random.Random(seed)
    q: dict[str, dict[str, float]] = {}

    def get_q(state: GameState, move: Move) -> float:
        k = _key(state)
        return q.get(k, {}).get(move.name, 0.0)

    def set_q(state: GameState, move: Move, val: float) -> None:
        k = _key(state)
        if k not in q:
            q[k] = {}
        q[k][move.name] = val

    def best_q(state: GameState) -> float:
        legal = legal_moves(state)
        if not legal:
            return 0.0
        return max(get_q(state, m) for m in legal)

    def choose(state: GameState) -> Move:
        legal = legal_moves(state)
        if not legal:
            return None
        if rng.random() < epsilon:
            return rng.choice(legal)
        best = max(legal, key=lambda m: get_q(state, m))
        return best

    for _ in range(episodes):
        state = _random_start(rng, config)
        for _step in range(config.max_moves):
            if is_capture(state) or is_timeout(state, config):
                break
            move = choose(state)
            if move is None:
                break
            next_state = apply_move(state, move)
            winner = None
            if is_capture(next_state):
                winner = "COP"
            elif is_timeout(next_state, config):
                winner = "THIEF"
            r = _reward(state, next_state, config, winner)
            old = get_q(state, move)
            new_val = old + alpha * (r + gamma * best_q(next_state) - old)
            set_q(state, move, new_val)
            state = next_state
            if winner:
                break

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(q, f, sort_keys=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Q-table for Cop & Thief")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    out = args.out or cfg.strategy["qtable"]["path"]
    print(f"Training {cfg.strategy['qtable']['train']['episodes']} episodes -> {out}")
    train(cfg, out)
    print("Done.")
