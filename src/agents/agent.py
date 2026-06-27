from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any

from src.game.board import Board
from src.game.moves import Move, legal_moves, apply_move
from src.game.state import GameState
from src.game.rules import is_capture
from src.strategy.evaluate import evaluate
from src.strategy.minimax import MinimaxMover
from src.agents.llm_client import LLMClient
from src.agents.prompts import OUTPUT_SCHEMA, system_prompt, render_observation


@dataclass
class AgentAction:
    move: Move
    message: str
    belief: tuple[int, int] | None = None
    confidence: str = "low"
    intent: str = "withhold"
    reasoning: str = ""
    llm: dict[str, Any] = field(default_factory=dict)


class Agent(Protocol):
    def act(self, observation: dict[str, Any], inbox: list[dict[str, Any]]) -> AgentAction:
        ...


_CONFIDENCE_MULTIPLIER = {"low": 0.3, "medium": 1.0, "high": 3.0}


def _clone_state(state: GameState) -> GameState:
    board = Board(state.board.rows, state.board.cols)
    board.barriers = set(state.board.barriers)
    return GameState(
        cop_pos=state.cop_pos,
        thief_pos=state.thief_pos,
        to_move=state.to_move,
        moves_used=state.moves_used,
        cop_barriers_left=state.cop_barriers_left,
        board=board,
    )


def _board_from_observation(observation: dict[str, Any]) -> Board:
    rows, cols = observation["grid"]
    board = Board(rows, cols)
    board.barriers = {tuple(barrier) for barrier in observation.get("barriers", [])}
    return board


def _tuple_pos(value) -> tuple[int, int] | None:
    if value is None:
        return None
    try:
        if len(value) != 2:
            return None
        return (int(value[0]), int(value[1]))
    except (TypeError, ValueError):
        return None


def _first_unblocked(board: Board) -> tuple[int, int]:
    for r in range(board.rows):
        for c in range(board.cols):
            pos = (r, c)
            if not board.is_blocked(pos):
                return pos
    return (0, 0)


def _fallback_unknown_opponent(board: Board) -> tuple[int, int]:
    center = (board.rows // 2, board.cols // 2)
    if not board.is_blocked(center):
        return center
    return _first_unblocked(board)


def _clamp_unblocked(pos: tuple[int, int], board: Board) -> tuple[int, int]:
    r = min(max(pos[0], 0), board.rows - 1)
    c = min(max(pos[1], 0), board.cols - 1)
    clamped = (r, c)
    if not board.is_blocked(clamped):
        return clamped
    return _first_unblocked(board)


def _parse_move_name(name: Any) -> Move | None:
    if not isinstance(name, str):
        return None
    return Move.__members__.get(name)


def _clean_confidence(value: Any) -> str:
    return value if value in _CONFIDENCE_MULTIPLIER else "low"


def _clean_intent(value: Any) -> str:
    allowed = {"probe", "deceive", "bait", "withhold", "trap", "truth"}
    return value if value in allowed else "withhold"


def _clean_message(value: Any) -> str:
    if not isinstance(value, str):
        return "Your story is getting thin."
    text = value.strip()
    return text if text else "Your story is getting thin."


class MoverAgent:
    def __init__(self, mover, role: str | None = None) -> None:
        self.mover = mover
        self.role = role

    def act(self, observation: dict[str, Any], inbox: list[dict[str, Any]]) -> AgentAction:
        state = observation.get("state")
        if state is None:
            raise ValueError("MoverAgent requires observation['state'] with full GameState")
        move = self.mover.choose_move(state)
        side = observation.get("role", self.role or state.to_move)
        return AgentAction(move=move, message=f"{side} plays {move.name}", intent="withhold")


class LLMAgent:
    def __init__(self, role: str, config, llm_client: LLMClient, minimax: MinimaxMover | None = None) -> None:
        self.role = role.upper()
        self.config = config
        self.llm = llm_client
        llm_cfg = config.agents["llm"]
        mm_cfg = config.strategy["minimax"]
        self.veto_margin = float(llm_cfg["veto_margin"])
        self.minimax = minimax or MinimaxMover(
            depth=mm_cfg["depth"],
            weights=mm_cfg["weights"],
            max_moves=config.max_moves,
        )

    def _belief_state(self, observation, guess) -> GameState:
        board = _board_from_observation(observation)
        self_pos = _clamp_unblocked(_tuple_pos(observation["self"]), board)
        seen_pos = _tuple_pos(observation.get("opponent_pos"))
        guess_pos = _tuple_pos(guess)

        if observation.get("sees_opponent") and seen_pos is not None:
            opponent_pos = _clamp_unblocked(seen_pos, board)
        elif guess_pos is not None:
            opponent_pos = _clamp_unblocked(guess_pos, board)
        else:
            opponent_pos = _fallback_unknown_opponent(board)

        moves_used = int(observation.get("moves_used", 0))
        cop_barriers_left = int(observation.get("cop_barriers_left", 0))
        if self.role == "COP":
            return GameState(
                cop_pos=self_pos,
                thief_pos=opponent_pos,
                to_move="COP",
                moves_used=moves_used,
                cop_barriers_left=cop_barriers_left,
                board=board,
            )
        return GameState(
            cop_pos=opponent_pos,
            thief_pos=self_pos,
            to_move="THIEF",
            moves_used=moves_used,
            cop_barriers_left=cop_barriers_left,
            board=board,
        )

    def _value_after(self, state: GameState, move: Move) -> float:
        return evaluate(apply_move(_clone_state(state), move), self.config)

    def _best_move_and_value(self, state: GameState) -> tuple[Move, float]:
        best_move = self.minimax.choose_move(state)
        return best_move, self._value_after(state, best_move)

    def _proposal_gap(self, role: str, proposed_value: float, best_value: float) -> float:
        if role == "COP":
            return best_value - proposed_value
        return proposed_value - best_value

    def _should_veto(
        self, state: GameState, proposed: Move | None, confidence: str, intent: str
    ) -> tuple[bool, Move]:
        moves = legal_moves(state)
        if proposed is None or proposed not in moves:
            return True, self.minimax.choose_move(state)

        if self.role == "THIEF" and is_capture(apply_move(_clone_state(state), proposed)):
            return True, self.minimax.choose_move(state)

        if self.role == "COP" and proposed is Move.PLACE_BARRIER and intent == "trap":
            return False, proposed

        best_move, best_value = self._best_move_and_value(state)
        proposed_value = self._value_after(state, proposed)
        gap = self._proposal_gap(self.role, proposed_value, best_value)
        if gap > self.veto_margin * _CONFIDENCE_MULTIPLIER[confidence]:
            return True, best_move
        return False, proposed

    def act(self, observation: dict[str, Any], inbox: list[dict[str, Any]]) -> AgentAction:
        obs = dict(observation)
        obs["role"] = self.role
        obs["max_moves"] = self.config.max_moves
        provisional_state = self._belief_state(obs, obs.get("opponent_pos"))
        obs["legal_moves"] = [move.name for move in legal_moves(provisional_state)]

        system = system_prompt(self.role, self.config)
        user = render_observation(obs, inbox)
        raw = self.llm.complete(system, user, OUTPUT_SCHEMA)

        guess = _tuple_pos(raw.get("opponent_guess"))
        confidence = _clean_confidence(raw.get("confidence"))
        intent = _clean_intent(raw.get("intent"))
        proposed = _parse_move_name(raw.get("move"))
        message = _clean_message(raw.get("message"))
        reasoning = str(raw.get("reasoning", ""))
        llm_meta = dict(raw.get("_llm", {}))

        belief_state = self._belief_state(obs, guess)
        veto, final_move = self._should_veto(belief_state, proposed, confidence, intent)
        if veto:
            llm_meta["vetoed"] = True
            llm_meta["proposed_move"] = raw.get("move")
            llm_meta["final_move"] = final_move.name
        else:
            llm_meta["vetoed"] = False

        belief = belief_state.thief_pos if self.role == "COP" else belief_state.cop_pos
        return AgentAction(
            move=final_move,
            message=message,
            belief=belief,
            confidence=confidence,
            intent=intent,
            reasoning=reasoning,
            llm=llm_meta,
        )
