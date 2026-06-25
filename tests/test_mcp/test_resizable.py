import dataclasses
from fastmcp import Client
from src.game.config import load_config
from src.mcp_servers.cop_server import build_cop_server


async def test_resizable_3x3():
    config = dataclasses.replace(load_config("config.yaml"), grid_size=(3, 3))
    server = build_cop_server(config)
    async with Client(server) as client:
        inside = await client.call_tool("validate_location", {"pos": [2, 2], "barriers": []})
        outside = await client.call_tool("validate_location", {"pos": [3, 3], "barriers": []})
    assert inside.data["ok"] is True
    assert outside.data["ok"] is False  # (3,3) is off a 3x3 board -> resizability proven
