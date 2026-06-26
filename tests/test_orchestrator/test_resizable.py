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


async def test_series_3x3_completes():
    """Full 6-sub-game series on 3×3 completes with group totals in [30, 90]."""
    config = _3x3()
    t = Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", t)
    thief_gw = InMemoryGateway(build_thief_server(config), "thief", t)
    async with cop_gw, thief_gw:
        result = await run_series(
            config, cop_gw, thief_gw, GreedyMover(), GreedyMover()
        )
    assert len(result.sub_games) == 6
    assert 30 <= result.group_a_total <= 90
    assert 30 <= result.group_b_total <= 90


async def test_every_move_validated_3x3():
    """validate_move is called exactly once per applied ply — no bypasses."""
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


async def test_grid_bounds_derived_from_config():
    """Servers must derive bounds from config.grid_size, not hard-coded 5×5."""
    config = _3x3()
    t = Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", t)
    async with cop_gw as gw:
        off_board = await gw.validate_location([3, 3], [])   # off 3x3 grid
        on_board = await gw.validate_location([2, 2], [])    # valid corner
    assert off_board["ok"] is False, "position (3,3) should be off a 3x3 grid"
    assert on_board["ok"] is True
