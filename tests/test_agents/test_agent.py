import copy
import dataclasses

from src.agents.agent import LLMAgent, MoverAgent
from src.agents.llm_client import FakeLLM
from src.game.board import Board
from src.game.config import load_config
from src.game.moves import Move
from src.game.state import GameState


def _config(*, veto_margin: float = 50.0):
    cfg = load_config("config.yaml")
    agents = copy.deepcopy(cfg.agents)
    agents["llm"]["veto_margin"] = veto_margin
    return dataclasses.replace(cfg, grid_size=(3, 3), max_moves=8, max_barriers=1, agents=agents)


def _observation(state: GameState, side: str, *, sees: bool = True) -> dict:
    self_pos = state.cop_pos if side == "COP" else state.thief_pos
    opp_pos = state.thief_pos if side == "COP" else state.cop_pos
    return {
        "mode": "full" if sees else "blind",
        "role": side,
        "self": list(self_pos),
        "grid": [state.board.rows, state.board.cols],
        "barriers": [list(b) for b in state.board.barriers],
        "moves_used": state.moves_used,
        "moves_left": 8 - state.moves_used,
        "max_moves": 8,
        "cop_barriers_left": state.cop_barriers_left,
        "sees_opponent": sees,
        "opponent_pos": list(opp_pos) if sees else None,
        "opponent_hint": "exact" if sees else "unseen",
        "inbox": [],
    }


def _script(move: str, *, confidence: str = "high", intent: str = "probe") -> list[dict]:
    return [
        {
            "opponent_guess": [2, 2],
            "confidence": confidence,
            "move": move,
            "message": "public taunt",
            "intent": intent,
            "reasoning": "private reason",
        }
    ]


def test_llm_agent_keeps_good_legal_proposal():
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    agent = LLMAgent("COP", _config(veto_margin=2.0), FakeLLM(_script("SE")))

    action = agent.act(_observation(state, "COP"), [])

    assert action.move is Move.SE
    assert action.llm["vetoed"] is False


def test_llm_agent_vetoes_unknown_move():
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    agent = LLMAgent("COP", _config(), FakeLLM(_script("NOPE")))

    action = agent.act(_observation(state, "COP"), [])

    assert action.move is Move.SE
    assert action.llm["vetoed"] is True
    assert action.llm["proposed_move"] == "NOPE"


def test_llm_agent_vetoes_thief_move_into_capture():
    state = GameState((1, 1), (0, 0), "THIEF", 0, 1, Board(3, 3))
    agent = LLMAgent("THIEF", _config(), FakeLLM(_script("SE")))

    action = agent.act(_observation(state, "THIEF"), [])

    assert action.move is not Move.SE
    assert action.llm["vetoed"] is True


def test_low_confidence_vetoes_more_than_high_confidence():
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    low = LLMAgent("COP", _config(veto_margin=2.0), FakeLLM(_script("S", confidence="low")))
    high = LLMAgent("COP", _config(veto_margin=2.0), FakeLLM(_script("S", confidence="high")))

    low_action = low.act(_observation(state, "COP"), [])
    high_action = high.act(_observation(state, "COP"), [])

    assert low_action.move is Move.SE
    assert low_action.llm["vetoed"] is True
    assert high_action.move is Move.S
    assert high_action.llm["vetoed"] is False


def test_cop_place_barrier_trap_exempt_from_eval_veto_when_legal():
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    agent = LLMAgent(
        "COP",
        _config(veto_margin=0.0),
        FakeLLM(_script("PLACE_BARRIER", confidence="low", intent="trap")),
    )

    action = agent.act(_observation(state, "COP"), [])

    assert action.move is Move.PLACE_BARRIER
    assert action.llm["vetoed"] is False


def test_mover_agent_wraps_existing_mover():
    class _Mover:
        def choose_move(self, state):
            return Move.S

    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    action = MoverAgent(_Mover(), role="COP").act({"state": state, "role": "COP"}, [])

    assert action.move is Move.S
    assert action.message == "COP plays S"
    assert action.intent == "withhold"


def test_hybrid_veto_keeps_good_move():
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    agent = LLMAgent("COP", _config(veto_margin=2.0), FakeLLM(_script("SE")))

    action = agent.act(_observation(state, "COP"), [])

    assert action.llm["vetoed"] is False
    assert action.move.name == "SE"


def test_hybrid_veto_overrides_blunder():
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    agent = LLMAgent("COP", _config(veto_margin=2.0), FakeLLM(_script("S", confidence="low")))

    action = agent.act(_observation(state, "COP"), [])

    assert action.move is not Move.S
    assert action.llm["vetoed"] is True
