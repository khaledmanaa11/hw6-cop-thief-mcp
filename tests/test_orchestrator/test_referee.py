import dataclasses
from src.game.config import load_config
from src.game.movers import GreedyMover
from src.mcp_servers.cop_server import build_cop_server
from src.mcp_servers.thief_server import build_thief_server
from src.orchestrator.gateway import InMemoryGateway
from src.orchestrator.recorders import Telemetry
from src.orchestrator.referee import run_series, run_sub_game


def _3x3():
    cfg = load_config("config.yaml")
    return dataclasses.replace(cfg, grid_size=(3, 3), max_moves=50, num_games=6)


def _gateways(config):
    t = Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", t)
    thief_gw = InMemoryGateway(build_thief_server(config), "thief", t)
    return cop_gw, thief_gw, t


async def test_greedy_cop_captures_3x3():
    config = _3x3()
    cop_gw, thief_gw, _ = _gateways(config)
    async with cop_gw, thief_gw:
        result = await run_sub_game(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover()
        )
    assert result.winner == "COP"


async def test_run_series_band():
    """6-sub-game series group totals must each be in [30, 90]."""
    config = _3x3()
    cop_gw, thief_gw, _ = _gateways(config)
    async with cop_gw, thief_gw:
        result = await run_series(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover()
        )
    assert len(result.sub_games) == config.num_games
    assert 30 <= result.group_a_total <= 90
    assert 30 <= result.group_b_total <= 90


async def test_every_move_validated():
    """validate_move call count must equal the number of plies in the transcript."""
    config = _3x3()
    t = Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", t)
    thief_gw = InMemoryGateway(build_thief_server(config), "thief", t)
    transcript: list = []
    async with cop_gw, thief_gw:
        await run_sub_game(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover(),
            transcript=transcript,
        )
    plies = len(transcript)
    validate_calls = sum(1 for name, _ in t._samples if name == "validate_move")
    assert validate_calls == plies
    assert plies > 0


async def test_message_bus_delivers():
    """Every ply record must include a message envelope."""
    config = _3x3()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []
    async with cop_gw, thief_gw:
        await run_sub_game(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover(),
            transcript=transcript,
        )
    assert len(transcript) > 0
    for record in transcript:
        assert "message" in record
        assert "from" in record["message"]
        assert "text" in record["message"]


async def test_envelope_has_no_coords():
    """Envelope must contain exactly {from, turn, ts, text} — no coordinate fields."""
    config = _3x3()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []
    async with cop_gw, thief_gw:
        await run_sub_game(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover(),
            transcript=transcript,
        )
    allowed = {"from", "turn", "ts", "text"}
    for record in transcript:
        env_keys = set(record["message"].keys())
        extra = env_keys - allowed
        assert not extra, f"unexpected envelope fields: {extra}"


async def test_sub_game_has_obs_both_sides():
    """Every ply record must have COP and THIEF observations."""
    config = _3x3()
    cop_gw, thief_gw, _ = _gateways(config)
    transcript: list = []
    async with cop_gw, thief_gw:
        await run_sub_game(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover(),
            transcript=transcript,
        )
    for record in transcript:
        assert "COP" in record["obs"]
        assert "THIEF" in record["obs"]
