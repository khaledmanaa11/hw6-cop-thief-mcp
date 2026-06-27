import copy
import dataclasses

from src.agents.agent import LLMAgent
from src.agents.factory import build_agent
from src.agents.llm_client import FakeLLM
from src.game.board import Board
from src.game.config import load_config
from src.game.moves import Move
from src.game.state import GameState
from src.mcp_servers.cop_server import build_cop_server
from src.mcp_servers.thief_server import build_thief_server
from src.orchestrator.gateway import InMemoryGateway
from src.orchestrator.recorders import Telemetry, belief_error
from src.orchestrator.referee import run_sub_game


def _config(*, veto_margin: float = 2.0, mode: str = "blind"):
    cfg = load_config("config.yaml")
    agents = copy.deepcopy(cfg.agents)
    agents["llm"]["veto_margin"] = veto_margin
    observation = dict(cfg.observation)
    observation["mode"] = mode
    return dataclasses.replace(
        cfg,
        grid_size=(3, 3),
        max_moves=8,
        max_barriers=1,
        agents=agents,
        observation=observation,
    )


def _observation(state: GameState, side: str) -> dict:
    self_pos = state.cop_pos if side == "COP" else state.thief_pos
    opp_pos = state.thief_pos if side == "COP" else state.cop_pos
    return {
        "mode": "blind",
        "role": side,
        "self": list(self_pos),
        "grid": [state.board.rows, state.board.cols],
        "barriers": [],
        "moves_used": state.moves_used,
        "moves_left": 8 - state.moves_used,
        "max_moves": 8,
        "cop_barriers_left": state.cop_barriers_left,
        "sees_opponent": False,
        "opponent_pos": None,
        "opponent_hint": "unseen",
        "inbox": [],
        "truth_for_test": list(opp_pos),
    }


def test_liar_persona_increases_belief_error():
    truth = (2, 2)
    user = "Sensor: opponent is at (2, 2). Your legal moves: N, S"

    honest = FakeLLM(persona="honest").complete([], user, {})
    liar = FakeLLM(persona="liar", decoy=(0, 0)).complete([], user, {})

    honest_error = belief_error(honest["opponent_guess"], truth)
    liar_error = belief_error(liar["opponent_guess"], truth)

    assert honest_error == 0
    assert liar_error > honest_error


async def test_reasoning_private_message_public():
    config = _config()
    telemetry = Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", telemetry)
    thief_gw = InMemoryGateway(build_thief_server(config), "thief", telemetry)
    transcript: list = []
    thief_script = [
        {
            "opponent_guess": [0, 0],
            "confidence": "high",
            "move": "N",
            "message": "public taunt",
            "intent": "deceive",
            "reasoning": "SECRET_TRUE_CELL",
        }
    ]

    async with cop_gw, thief_gw:
        await run_sub_game(
            config,
            cop_gw,
            thief_gw,
            build_agent("cop", config, FakeLLM()),
            build_agent("thief", config, FakeLLM(thief_script)),
            transcript=transcript,
        )

    assert any(record["action"]["reasoning"] == "SECRET_TRUE_CELL" for record in transcript)
    assert all("SECRET_TRUE_CELL" not in record["message"]["text"] for record in transcript)


def test_confidence_weighted_veto_regime():
    config = _config(veto_margin=2.0)
    state = GameState((0, 0), (2, 2), "COP", 0, 1, Board(3, 3))
    low = LLMAgent(
        "COP",
        config,
        FakeLLM(
            [
                {
                    "opponent_guess": [2, 2],
                    "confidence": "low",
                    "move": "S",
                    "message": "low confidence",
                    "intent": "probe",
                    "reasoning": "private",
                }
            ]
        ),
    )
    high = LLMAgent(
        "COP",
        config,
        FakeLLM(
            [
                {
                    "opponent_guess": [2, 2],
                    "confidence": "high",
                    "move": "S",
                    "message": "high confidence",
                    "intent": "probe",
                    "reasoning": "private",
                }
            ]
        ),
    )

    low_action = low.act(_observation(state, "COP"), [])
    high_action = high.act(_observation(state, "COP"), [])

    assert low_action.llm["vetoed"] is True
    assert low_action.move is Move.SE
    assert high_action.llm["vetoed"] is False
    assert high_action.move is Move.S
