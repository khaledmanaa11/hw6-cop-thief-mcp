import dataclasses
import json
import tempfile

from src.game.board import Board
from src.game.config import load_config
from src.game.movers import GreedyMover
from src.game.state import GameState, initial_state
from src.mcp_servers.cop_server import build_cop_server
from src.mcp_servers.thief_server import build_thief_server
from src.orchestrator.gateway import InMemoryGateway
from src.orchestrator.recorders import ReplayLog, Telemetry, observe, render_board
from src.orchestrator.referee import run_sub_game


def _3x3():
    cfg = load_config("config.yaml")
    return dataclasses.replace(cfg, grid_size=(3, 3), max_moves=50, num_games=2)


def test_observe_schema_cop():
    config = _3x3()
    state = initial_state(config)
    view = observe(state, "COP")
    assert set(view.keys()) == {"self", "sees_opponent", "opponent_pos", "last_msg", "barriers"}
    assert view["self"] == list(state.cop_pos)
    assert view["sees_opponent"] is True
    assert view["opponent_pos"] == list(state.thief_pos)
    assert view["last_msg"] is None


def test_observe_schema_thief():
    config = _3x3()
    state = initial_state(config)
    view = observe(state, "THIEF")
    assert view["self"] == list(state.thief_pos)
    assert view["opponent_pos"] == list(state.cop_pos)


def test_observe_last_msg():
    config = _3x3()
    state = initial_state(config)
    view = observe(state, "COP", last_msg="THIEF plays N")
    assert view["last_msg"] == "THIEF plays N"


def test_render_board_3x3():
    board = Board(3, 3)
    board.barriers.add((1, 1))
    state = GameState(
        cop_pos=(0, 0),
        thief_pos=(2, 2),
        to_move="THIEF",
        moves_used=0,
        cop_barriers_left=5,
        board=board,
    )
    rendered = render_board(state)
    lines = rendered.split("\n")
    assert len(lines) == 3
    assert lines[0][0] == "C"
    assert lines[2][-1] == "T"
    assert "#" in lines[1]


def test_render_board_no_barriers():
    board = Board(3, 3)
    state = GameState(
        cop_pos=(0, 0), thief_pos=(2, 2),
        to_move="THIEF", moves_used=0, cop_barriers_left=5, board=board,
    )
    rendered = render_board(state)
    assert "#" not in rendered
    assert "C" in rendered
    assert "T" in rendered


async def test_replay_log_roundtrip():
    config = _3x3()
    t = Telemetry()
    cop_gw = InMemoryGateway(build_cop_server(config), "cop", t)
    thief_gw = InMemoryGateway(build_thief_server(config), "thief", t)
    transcript: list = []
    with tempfile.TemporaryDirectory() as tmpdir:
        replay = ReplayLog(tmpdir)
        async with cop_gw, thief_gw:
            await run_sub_game(
                config, cop_gw, thief_gw, GreedyMover(), GreedyMover(),
                transcript=transcript, replay_log=replay,
            )
        replay.close()
        with open(replay.path, encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
    assert len(lines) == len(transcript)
    for line in lines:
        parsed = json.loads(line)
        assert "turn" in parsed
        assert "side" in parsed
        assert "move" in parsed
