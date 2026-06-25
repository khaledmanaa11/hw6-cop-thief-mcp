from fastmcp import Client
from src.game.config import load_config
from src.mcp_servers.thief_server import build_thief_server


def _config():
    return load_config("config.yaml")


async def test_ping_thief():
    server = build_thief_server(_config())
    async with Client(server) as client:
        result = await client.call_tool("ping", {})
    assert result.data["ok"] is True
    assert result.data["server"] == "thief"


async def test_thief_validate_location_and_message():
    server = build_thief_server(_config())
    async with Client(server) as client:
        loc = await client.call_tool("validate_location", {"pos": [1, 1], "barriers": []})
        msg = await client.call_tool("send_message", {"envelope": {
            "from": "thief", "turn": 2, "ts": "t", "text": "you'll never catch me — I'm heading nowhere near you",
        }})
    assert loc.data["ok"] is True
    assert msg.data["ok"] is True


async def test_asymmetry_place_barrier():
    server = build_thief_server(_config())
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
    assert "place_barrier" not in names
    assert {"ping", "validate_location", "validate_move", "send_message"} <= names
