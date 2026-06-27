import dataclasses

from src.agents.factory import build_agent
from src.agents.llm_client import FakeLLM
from src.game.config import load_config
from src.mcp_servers.cop_server import build_cop_server
from src.mcp_servers.thief_server import build_thief_server
from src.orchestrator.gateway import InMemoryGateway
from src.orchestrator.recorders import Telemetry
from src.orchestrator.referee import run_series, run_sub_game


def _config(*, mode: str = "noisy"):
    cfg = load_config("config.yaml")
    observation = dict(cfg.observation)
    observation["mode"] = mode
    return dataclasses.replace(
        cfg,
        grid_size=(3, 3),
        max_moves=8,
        num_games=2,
        max_barriers=1,
        observation=observation,
    )


def _gateways(config, telemetry: Telemetry | None = None):
    telemetry = telemetry or Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", telemetry)
    thief_gw = InMemoryGateway(build_thief_server(config), "thief", telemetry)
    return cop_gw, thief_gw, telemetry


def _agent(role: str, config, script=None):
    return build_agent(role.lower(), config, FakeLLM(script))


def _script(*, move="N", message="public taunt", reasoning="private reason", guess=None):
    return [
        {
            "opponent_guess": guess,
            "confidence": "high",
            "move": move,
            "message": message,
            "intent": "probe",
            "reasoning": reasoning,
        }
    ]


async def test_telemetry_records_one_llm_sample_per_agent_decision():
    config = _config()
    telemetry = Telemetry()
    cop_gw, thief_gw, _ = _gateways(config, telemetry)
    transcript: list = []

    async with cop_gw, thief_gw:
        await run_sub_game(
            config,
            cop_gw,
            thief_gw,
            _agent("COP", config),
            _agent("THIEF", config),
            transcript=transcript,
        )

    summary = telemetry.summary()
    assert summary["llm_calls"] == len(transcript)
    assert summary["llm_calls"] > 0
    assert summary["llm_input_tokens"] > 0


async def test_real_nl_channel_delivers_message_to_opponent_next_observation():
    config = _config()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []

    async with cop_gw, thief_gw:
        await run_sub_game(
            config,
            cop_gw,
            thief_gw,
            _agent("COP", config),
            _agent("THIEF", config, _script(message="I am nowhere near you.")),
            transcript=transcript,
        )

    first = transcript[0]
    recipient = "THIEF" if first["side"] == "COP" else "COP"
    assert first["obs"][recipient]["inbox"][-1] == first["message"]
    assert first["message"]["text"] == "I am nowhere near you."


async def test_message_envelope_has_no_coordinate_fields():
    config = _config()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []

    async with cop_gw, thief_gw:
        await run_sub_game(
            config,
            cop_gw,
            thief_gw,
            _agent("COP", config),
            _agent("THIEF", config),
            transcript=transcript,
        )

    for record in transcript:
        assert set(record["message"].keys()) == {"from", "turn", "ts", "text"}


async def test_reasoning_logged_but_never_sent_in_envelope():
    config = _config()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []

    async with cop_gw, thief_gw:
        await run_sub_game(
            config,
            cop_gw,
            thief_gw,
            _agent("COP", config),
            _agent(
                "THIEF",
                config,
                _script(message="public taunt", reasoning="SECRET_TRUE_CELL"),
            ),
            transcript=transcript,
        )

    assert any(record["action"]["reasoning"] == "SECRET_TRUE_CELL" for record in transcript)
    assert all("SECRET_TRUE_CELL" not in record["message"]["text"] for record in transcript)


async def test_belief_and_belief_error_recorded():
    config = _config(mode="blind")
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []

    async with cop_gw, thief_gw:
        await run_sub_game(
            config,
            cop_gw,
            thief_gw,
            _agent("COP", config),
            _agent("THIEF", config, _script(guess=[1, 1])),
            transcript=transcript,
        )

    first = transcript[0]
    assert first["action"]["belief"] == [1, 1]
    assert first["action"]["belief_error"] == 1
    assert "action" in first
    assert "message" in first


async def test_fake_llm_series_runs_on_3x3_inmemory_gateway():
    config = _config()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []

    def group_factory(runtime_role: str):
        return build_agent(runtime_role.lower(), config, FakeLLM())

    async with cop_gw, thief_gw:
        result = await run_series(
            config,
            cop_gw,
            thief_gw,
            group_factory,
            group_factory,
            transcript=transcript,
        )

    assert len(result.sub_games) == config.num_games
    assert result.group_a_total >= 0
    assert result.group_b_total >= 0
    assert transcript


async def test_no_network_no_key_full_fake_series(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = _config()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []

    def group_factory(runtime_role: str):
        return build_agent(runtime_role.lower(), config, FakeLLM())

    async with cop_gw, thief_gw:
        result = await run_series(
            config,
            cop_gw,
            thief_gw,
            group_factory,
            group_factory,
            transcript=transcript,
        )

    assert len(result.sub_games) == config.num_games
    assert result.group_a_total >= 0
    assert result.group_b_total >= 0
    assert transcript
