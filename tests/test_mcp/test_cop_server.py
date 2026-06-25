from fastmcp import Client
from src.game.config import load_config
from src.mcp_servers.cop_server import build_cop_server

from src.game.board import Board
from src.game.state import GameState
from src.game.moves import Move, legal_moves


def _config():
    return load_config("config.yaml")


async def test_ping_cop():
    server = build_cop_server(_config())
    async with Client(server) as client:
        result = await client.call_tool("ping", {})
    assert result.data["ok"] is True
    assert result.data["server"] == "cop"
    assert result.data["reason"]


async def test_validate_location_cop():
    server = build_cop_server(_config())
    async with Client(server) as client:
        on = await client.call_tool("validate_location", {"pos": [0, 0], "barriers": []})
        off = await client.call_tool("validate_location", {"pos": [99, 99], "barriers": []})
        blocked = await client.call_tool("validate_location", {"pos": [2, 2], "barriers": [[2, 2]]})
    assert on.data["ok"] is True and on.data["reason"]
    assert off.data["ok"] is False and off.data["reason"]
    assert blocked.data["ok"] is False and "barrier" in blocked.data["reason"].lower()


async def test_validate_move_agrees_with_engine():
    config = _config()
    # Thief at (2,2) on a 5x5 board: SE -> (3,3) is legal; building the same state for the engine.
    board = Board(*config.grid_size)
    state = GameState((0, 0), (2, 2), "THIEF", 0, config.max_barriers, board)
    engine_legal = Move.SE in legal_moves(state)
    server = build_cop_server(config)
    async with Client(server) as client:
        r = await client.call_tool("validate_move", {
            "to_move": "THIEF", "cop_pos": [0, 0], "thief_pos": [2, 2],
            "cop_barriers_left": config.max_barriers, "barriers": [], "move": "SE",
        })
    assert r.data["ok"] is engine_legal is True
    assert r.data["reason"]


async def test_validate_move_rejects_offboard():
    server = build_cop_server(_config())
    async with Client(server) as client:
        r = await client.call_tool("validate_move", {
            "to_move": "THIEF", "cop_pos": [0, 0], "thief_pos": [0, 0],
            "cop_barriers_left": 5, "barriers": [], "move": "NW",
        })
    assert r.data["ok"] is False
    assert r.data["reason"]


async def test_send_message_free_text():
    server = build_cop_server(_config())
    envelope = {
        "from": "cop", "turn": 3, "ts": "2026-06-25T10:00:00",
        "text": "I think you're hiding near the north wall — are you bluffing?",
    }
    async with Client(server) as client:
        r = await client.call_tool("send_message", {"envelope": envelope})
    assert r.data["ok"] is True
    assert "cop" in r.data["reason"]


async def test_send_message_schema_has_no_coords():
    server = build_cop_server(_config())
    async with Client(server) as client:
        tool_list = await client.list_tools()
    send = next(t for t in tool_list if t.name == "send_message")
    props = set(send.inputSchema.get("properties", {}).keys())
    assert props == {"envelope"}
    forbidden = {"row", "col", "x", "y", "pos", "position"}
    assert not (props & forbidden)


async def test_place_barrier_cop():
    server = build_cop_server(_config())
    async with Client(server) as client:
        ok = await client.call_tool("place_barrier", {"pos": [2, 2], "cop_barriers_left": 5, "barriers": []})
        dup = await client.call_tool("place_barrier", {"pos": [2, 2], "cop_barriers_left": 5, "barriers": [[2, 2]]})
        none_left = await client.call_tool("place_barrier", {"pos": [2, 2], "cop_barriers_left": 0, "barriers": []})
    assert ok.data["ok"] is True
    assert dup.data["ok"] is False
    assert none_left.data["ok"] is False


async def test_cop_has_place_barrier():
    server = build_cop_server(_config())
    async with Client(server) as client:
        names = {t.name for t in await client.list_tools()}
    assert "place_barrier" in names
    assert {"ping", "validate_location", "validate_move", "send_message"} <= names
