import dataclasses
from src.game.config import load_config
from src.mcp_servers.cop_server import build_cop_server
from src.orchestrator.gateway import InMemoryGateway
from src.orchestrator.recorders import Telemetry


def _config():
    return load_config("config.yaml")


async def test_gateway_inmemory_ping():
    config = _config()
    telemetry = Telemetry()
    server = build_cop_server(config)
    async with InMemoryGateway(server, "cop", telemetry) as gw:
        result = await gw.ping()
    assert result["ok"] is True
    assert result["server"] == "cop"
    assert telemetry.summary()["calls"] == 1


async def test_gateway_records_one_sample_per_call():
    config = _config()
    telemetry = Telemetry()
    server = build_cop_server(config)
    async with InMemoryGateway(server, "cop", telemetry) as gw:
        await gw.ping()
        await gw.validate_location([0, 0], [])
        await gw.validate_move("COP", [0, 0], [4, 4], 5, [], "S")
    assert telemetry.summary()["calls"] == 3


async def test_gateway_validate_move_returns_ok_dict():
    config = _config()
    telemetry = Telemetry()
    server = build_cop_server(config)
    async with InMemoryGateway(server, "cop", telemetry) as gw:
        result = await gw.validate_move("COP", [0, 0], [4, 4], 5, [], "S")
    assert "ok" in result
    assert "reason" in result
    assert result["ok"] is True


async def test_gateway_send_message():
    config = _config()
    telemetry = Telemetry()
    server = build_cop_server(config)
    envelope = {"from": "COP", "turn": 1, "ts": "2026-01-01T00:00:00+00:00", "text": "hello"}
    async with InMemoryGateway(server, "cop", telemetry) as gw:
        result = await gw.send_message(envelope)
    assert result["ok"] is True
