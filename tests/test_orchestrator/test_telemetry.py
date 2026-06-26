from src.game.config import load_config
from src.mcp_servers.cop_server import build_cop_server
from src.orchestrator.gateway import InMemoryGateway
from src.orchestrator.recorders import Telemetry


def test_telemetry_records_samples():
    t = Telemetry()
    t.record("ping", 5.0)
    t.record("validate_move", 3.0)
    s = t.summary()
    assert s["calls"] == 2
    assert isinstance(s["avg_ms"], float)
    assert isinstance(s["p95_ms"], float)
    assert s["avg_ms"] == 4.0


def test_telemetry_empty():
    t = Telemetry()
    s = t.summary()
    assert s["calls"] == 0
    assert s["avg_ms"] == 0.0
    assert s["p95_ms"] == 0.0


def test_telemetry_boot_ping():
    t = Telemetry()
    t.set_boot_ping(10.5, 12.3)
    s = t.summary()
    assert s["boot_ping"]["cop_ms"] == 10.5
    assert s["boot_ping"]["thief_ms"] == 12.3


async def test_telemetry_one_sample_per_call():
    """Gateway must record exactly one timing sample per tool call."""
    config = load_config("config.yaml")
    t = Telemetry()
    server = build_cop_server(config)
    async with InMemoryGateway(server, "cop", t) as gw:
        await gw.ping()
        await gw.validate_location([0, 0], [])
        await gw.validate_move("COP", [0, 0], [4, 4], 5, [], "S")
    assert t.summary()["calls"] == 3
    tool_names = [name for name, _ in t._samples]
    assert tool_names == ["ping", "validate_location", "validate_move"]
