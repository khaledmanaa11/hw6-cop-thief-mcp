# TODO — Step 2: Basic MCP infrastructure

> Implements `PRD_step2_mcp_infra.md` + `PLAN_step2_mcp_infra.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never hard-code** game parameters or ports — read them from `config.yaml` / `Config`.
4. Do not assume a 5×5 grid; bounds always come from `config.grid_size`.
5. If a box seems ambiguous, STOP and ask — do not guess.
6. Keep each file focused; do not add tools or features not listed here.
7. **Run every command from the repository root** (the folder containing `config.yaml`).
8. **Do NOT add** `get_state`, `apply_move`, inbox, scoring, or reset tools — they belong to Step 3. Adding them breaks the "plumbing only" boundary.

## Conventions
- Language/runtime: **Python 3.12**. Source root: `src/` · Tests: `tests/`.
- Each box format: **ID · file · action · detail · Check.**
- **Library:** the standalone **`fastmcp`** package (3.x). Import as `from fastmcp import FastMCP, Client`.
- **Servers are STATELESS.** No module-level game state. Every tool that needs board context takes it as a call argument.
- **Every tool returns a `dict`** of the shape `{ "ok": bool, "reason": str, ... }`. Through the in-memory client, that dict is read back as `result.data` (e.g. `result.data["ok"]`).
- **`tools.py` holds the real logic** as plain functions; the server files just wrap those functions with `@mcp.tool`. Do not duplicate logic between the two servers.
- **Move names** are the `Move` enum members from `src/game/moves.py`: `N S E W NE NW SE SW PLACE_BARRIER`. Resolve a name string with `Move[name]`.
- **The message envelope** is a dict `{ "from": str, "turn": int, "ts": str, "text": str }`. `text` is free natural language. There are **NO** coordinate fields. Never add a `row`/`col`/`x`/`y`/`pos` field to the message schema.

---

## Phase A — dependencies & config

- [x] **A1** — `requirements.txt` — edit — append two lines so the file reads exactly:
      ```
      pyyaml
      pytest
      fastmcp
      pytest-asyncio
      ```
      Then install: `pip install -r requirements.txt`.
      **Check:** `python -c "import fastmcp, pytest_asyncio; print('ok')"` prints `ok`.

- [x] **A2** — `pyproject.toml` — edit — add the `asyncio_mode` line so async tests run without per-test markers. The file must read exactly:
      ```toml
      [tool.pytest.ini_options]
      pythonpath = ["."]
      asyncio_mode = "auto"
      ```
      **Check:** `python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['pytest']['ini_options']['asyncio_mode'])"` prints `auto`.

- [x] **A3** — `config.yaml` — edit — append a `servers:` block at the end (keep all existing keys unchanged). The full file becomes:
      ```yaml
      grid_size: [5, 5]
      max_moves: 25
      num_games: 6
      max_barriers: 5
      scoring:
        cop_win: 20
        thief_win: 10
        cop_loss: 5
        thief_loss: 5
      servers:
        cop:
          host: "127.0.0.1"
          port: 8001
        thief:
          host: "127.0.0.1"
          port: 8002
      ```
      **Check:** `python -c "import yaml; d=yaml.safe_load(open('config.yaml')); print(d['servers']['cop']['port'], d['servers']['thief']['port'])"` prints `8001 8002`.

- [x] **A4** — `src/game/config.py` — edit — add two dataclasses **above** the existing `Config` class:
      ```python
      @dataclass
      class ServerEndpoint:
          host: str
          port: int


      @dataclass
      class ServersConfig:
          cop: ServerEndpoint
          thief: ServerEndpoint
      ```
      (Do not change `ScoringConfig`.)
      **Check:** `python -c "from src.game.config import ServerEndpoint, ServersConfig; print(ServerEndpoint('127.0.0.1', 8001))"` exits 0.

- [x] **A5** — `src/game/config.py` — edit — add a new field to the `Config` dataclass **as the last field, with a default** so existing constructions keep working:
      ```python
      servers: ServersConfig | None = None
      ```
      **Check:** `python -c "from src.game.config import Config; print('servers' in Config.__dataclass_fields__)"` prints `True`.

- [x] **A6** — `src/game/config.py` — edit — in `load_config`, **after** building `scoring` and **before** the final `return Config(...)`, parse an optional `servers:` block:
      ```python
      servers = None
      if "servers" in data:
          sv = data["servers"]
          def _endpoint(d):
              host = d["host"]
              port = d["port"]
              if not host:
                  raise ValueError("server host must be non-empty")
              if not (1 <= port <= 65535):
                  raise ValueError(f"server port out of range: {port}")
              return ServerEndpoint(host=host, port=port)
          servers = ServersConfig(cop=_endpoint(sv["cop"]), thief=_endpoint(sv["thief"]))
      ```
      Then add `servers=servers,` to the `return Config(...)` call (keep all existing args).
      **Check:** `python -c "from src.game.config import load_config; c=load_config('config.yaml'); print(c.servers.cop.port, c.servers.thief.host)"` prints `8001 127.0.0.1`.

## Phase B — adapter functions (`tools.py`)

- [x] **B1** — `src/mcp_servers/__init__.py` — create — empty file so `src.mcp_servers` is an importable package.
      **Check:** `python -c "import src.mcp_servers"` exits 0 (run from repo root).

- [x] **B2** — `src/mcp_servers/tools.py` — create — add the imports and the board helper. **Do not import `fastmcp` in this file.**
      ```python
      from src.game.board import Board
      from src.game.state import GameState
      from src.game.moves import Move, legal_moves


      def _board_with_barriers(config, barriers) -> Board:
          rows, cols = config.grid_size
          board = Board(rows, cols)
          for b in barriers:
              board.barriers.add(tuple(b))
          return board
      ```
      **Check:** `python -c "from src.mcp_servers.tools import _board_with_barriers"` exits 0.

- [x] **B3** — `src/mcp_servers/tools.py` — extend — add `ping_result`:
      ```python
      def ping_result(server_name: str) -> dict:
          return {"ok": True, "server": server_name, "reason": f"{server_name} server alive"}
      ```
      **Check:** `python -c "from src.mcp_servers.tools import ping_result; print(ping_result('cop'))"` prints `{'ok': True, 'server': 'cop', 'reason': 'cop server alive'}`.

- [x] **B4** — `src/mcp_servers/tools.py` — extend — add `validate_location_result`:
      ```python
      def validate_location_result(pos, barriers, config) -> dict:
          pos = tuple(pos)
          board = _board_with_barriers(config, barriers)
          if not board.in_bounds(pos):
              return {"ok": False, "reason": f"off-board: {pos} outside grid {config.grid_size}"}
          if board.is_blocked(pos):
              return {"ok": False, "reason": f"blocked: barrier at {pos}"}
          return {"ok": True, "reason": f"clear: {pos} is on-board and unblocked"}
      ```
      **Check:** `python -c "from src.game.config import load_config; from src.mcp_servers.tools import validate_location_result as v; c=load_config('config.yaml'); print(v([0,0],[],c)['ok'], v([9,9],[],c)['ok'], v([2,2],[[2,2]],c)['ok'])"` prints `True False False`.

- [x] **B5** — `src/mcp_servers/tools.py` — extend — add `validate_move_result`. It builds a `GameState` and asks the Step-1 engine — **do not re-implement movement rules**:
      ```python
      def validate_move_result(to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move, config) -> dict:
          board = _board_with_barriers(config, barriers)
          state = GameState(
              cop_pos=tuple(cop_pos),
              thief_pos=tuple(thief_pos),
              to_move=to_move,
              moves_used=0,
              cop_barriers_left=cop_barriers_left,
              board=board,
          )
          try:
              mv = Move[move]
          except KeyError:
              return {"ok": False, "reason": f"unknown move '{move}'"}
          if mv in legal_moves(state):
              return {"ok": True, "reason": f"legal: {move} for {to_move}"}
          return {"ok": False, "reason": f"illegal: {move} for {to_move} (off-board, blocked, or not allowed)"}
      ```
      **Check:** `python -c "from src.game.config import load_config; from src.mcp_servers.tools import validate_move_result as v; c=load_config('config.yaml'); print(v('THIEF',[0,0],[4,4],5,[],'NW',c)['ok'], v('THIEF',[0,0],[0,0],5,[],'N',c)['ok'])"` prints `False True` (Thief at (0,0): `N`→(-1,0) is off-board ⇒ illegal; Thief at corner (4,4) would matter — here Thief is at thief_pos=(0,0) since to_move=THIEF, so `NW` off-board ⇒ False, `N` from (0,0)… also off-board). **Expected actual output: `False False`.** Confirm both are `False` because both targets leave the board from corner (0,0); then run the next sanity line: `python -c "from src.game.config import load_config; from src.mcp_servers.tools import validate_move_result as v; c=load_config('config.yaml'); print(v('THIEF',[0,0],[2,2],5,[],'SE',c)['ok'])"` prints `True`.

- [x] **B6** — `src/mcp_servers/tools.py` — extend — add `send_message_result`. The envelope is a dict; validate its keys and that `text` is a string. **No coordinate fields are involved.**
      ```python
      def send_message_result(envelope) -> dict:
          required = ("from", "turn", "ts", "text")
          missing = [k for k in required if k not in envelope]
          if missing:
              return {"ok": False, "reason": f"missing fields: {missing}"}
          if not isinstance(envelope["text"], str):
              return {"ok": False, "reason": "text must be a string"}
          return {"ok": True, "reason": f"message accepted from {envelope['from']} at turn {envelope['turn']}"}
      ```
      **Check:** `python -c "from src.mcp_servers.tools import send_message_result as s; print(s({'from':'cop','turn':1,'ts':'t','text':'where are you, thief?'})['ok'], s({'from':'cop'})['ok'])"` prints `True False`.

- [x] **B7** — `src/mcp_servers/tools.py` — extend — add `place_barrier_result`. **Validation only — never call `board.place_barrier`; never mutate anything.**
      ```python
      def place_barrier_result(pos, cop_barriers_left, barriers, config) -> dict:
          pos = tuple(pos)
          board = _board_with_barriers(config, barriers)
          if cop_barriers_left <= 0:
              return {"ok": False, "reason": "no barriers left"}
          if not board.in_bounds(pos):
              return {"ok": False, "reason": f"off-board: {pos} outside grid {config.grid_size}"}
          if board.is_blocked(pos):
              return {"ok": False, "reason": f"barrier already at {pos}"}
          return {"ok": True, "reason": f"valid barrier site: {pos}"}
      ```
      **Check:** `python -c "from src.game.config import load_config; from src.mcp_servers.tools import place_barrier_result as p; c=load_config('config.yaml'); print(p([2,2],5,[],c)['ok'], p([2,2],0,[],c)['ok'], p([2,2],5,[[2,2]],c)['ok'], p([9,9],5,[],c)['ok'])"` prints `True False False False`.

## Phase C — Cop server

- [x] **C1** — `src/mcp_servers/cop_server.py` — create — imports and the builder header:
      ```python
      from fastmcp import FastMCP
      from src.game.config import load_config
      from src.mcp_servers import tools


      def build_cop_server(config) -> FastMCP:
          mcp = FastMCP("cop")
      ```
      (The tool registrations are added in the next boxes, indented inside `build_cop_server`.)
      **Check:** file exists; do not import yet (it is incomplete until C6). Skip running until C6.

- [x] **C2** — `src/mcp_servers/cop_server.py` — extend — inside `build_cop_server`, register `ping` and `validate_location`:
      ```python
          @mcp.tool
          def ping() -> dict:
              return tools.ping_result("cop")

          @mcp.tool
          def validate_location(pos: list[int], barriers: list[list[int]]) -> dict:
              return tools.validate_location_result(pos, barriers, config)
      ```
      **Check:** none yet (still inside the function); proceed.

- [x] **C3** — `src/mcp_servers/cop_server.py` — extend — register `validate_move`:
      ```python
          @mcp.tool
          def validate_move(
              to_move: str,
              cop_pos: list[int],
              thief_pos: list[int],
              cop_barriers_left: int,
              barriers: list[list[int]],
              move: str,
          ) -> dict:
              return tools.validate_move_result(
                  to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move, config
              )
      ```
      **Check:** none yet; proceed.

- [x] **C4** — `src/mcp_servers/cop_server.py` — extend — register `send_message` (its only parameter is the opaque `envelope` dict — **no coordinate fields**):
      ```python
          @mcp.tool
          def send_message(envelope: dict) -> dict:
              return tools.send_message_result(envelope)
      ```
      **Check:** none yet; proceed.

- [x] **C5** — `src/mcp_servers/cop_server.py` — extend — register `place_barrier` (**Cop server ONLY**):
      ```python
          @mcp.tool
          def place_barrier(pos: list[int], cop_barriers_left: int, barriers: list[list[int]]) -> dict:
              return tools.place_barrier_result(pos, cop_barriers_left, barriers, config)
      ```
      **Check:** none yet; proceed.

- [x] **C6** — `src/mcp_servers/cop_server.py` — extend — close the builder with `return mcp`, then add the `__main__` launcher. Append at module level (NOT indented inside the builder):
      ```python
          return mcp


      if __name__ == "__main__":
          config = load_config("config.yaml")
          mcp = build_cop_server(config)
          mcp.run(
              transport="http",
              host=config.servers.cop.host,
              port=config.servers.cop.port,
          )
      ```
      **Check:** `python -c "from src.game.config import load_config; from src.mcp_servers.cop_server import build_cop_server; m=build_cop_server(load_config('config.yaml')); print(type(m).__name__)"` prints `FastMCP`.

## Phase D — Thief server

- [x] **D1** — `src/mcp_servers/thief_server.py` — create — same shape as the Cop server **but with NO `place_barrier` tool** and `server_name="thief"`. Full file:
      ```python
      from fastmcp import FastMCP
      from src.game.config import load_config
      from src.mcp_servers import tools


      def build_thief_server(config) -> FastMCP:
          mcp = FastMCP("thief")

          @mcp.tool
          def ping() -> dict:
              return tools.ping_result("thief")

          @mcp.tool
          def validate_location(pos: list[int], barriers: list[list[int]]) -> dict:
              return tools.validate_location_result(pos, barriers, config)

          @mcp.tool
          def validate_move(
              to_move: str,
              cop_pos: list[int],
              thief_pos: list[int],
              cop_barriers_left: int,
              barriers: list[list[int]],
              move: str,
          ) -> dict:
              return tools.validate_move_result(
                  to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move, config
              )

          @mcp.tool
          def send_message(envelope: dict) -> dict:
              return tools.send_message_result(envelope)

          return mcp


      if __name__ == "__main__":
          config = load_config("config.yaml")
          mcp = build_thief_server(config)
          mcp.run(
              transport="http",
              host=config.servers.thief.host,
              port=config.servers.thief.port,
          )
      ```
      **Check:** `python -c "from src.game.config import load_config; from src.mcp_servers.thief_server import build_thief_server; m=build_thief_server(load_config('config.yaml')); print(type(m).__name__)"` prints `FastMCP`.

## Phase E — tests (in-memory Client)

- [x] **E1** — `tests/test_mcp/__init__.py` — create — empty file so the test package imports.
      **Check:** file exists.

- [x] **E2** — `tests/test_mcp/test_cop_server.py` — create — header + a shared config fixture and a server builder. Start the file with:
      ```python
      from fastmcp import Client
      from src.game.config import load_config
      from src.mcp_servers.cop_server import build_cop_server


      def _config():
          return load_config("config.yaml")
      ```
      **Check:** `python -c "import ast; ast.parse(open('tests/test_mcp/test_cop_server.py').read()); print('ok')"` prints `ok`.

- [x] **E3** — `tests/test_mcp/test_cop_server.py` — extend — add `test_ping_cop` (async, no marker needed — `asyncio_mode=auto`):
      ```python
      async def test_ping_cop():
          server = build_cop_server(_config())
          async with Client(server) as client:
              result = await client.call_tool("ping", {})
          assert result.data["ok"] is True
          assert result.data["server"] == "cop"
          assert result.data["reason"]
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_ping_cop -q` passes.

- [x] **E4** — `tests/test_mcp/test_cop_server.py` — extend — add `test_validate_location_cop`:
      ```python
      async def test_validate_location_cop():
          server = build_cop_server(_config())
          async with Client(server) as client:
              on = await client.call_tool("validate_location", {"pos": [0, 0], "barriers": []})
              off = await client.call_tool("validate_location", {"pos": [99, 99], "barriers": []})
              blocked = await client.call_tool("validate_location", {"pos": [2, 2], "barriers": [[2, 2]]})
          assert on.data["ok"] is True and on.data["reason"]
          assert off.data["ok"] is False and off.data["reason"]
          assert blocked.data["ok"] is False and "barrier" in blocked.data["reason"].lower()
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_validate_location_cop -q` passes.

- [x] **E5** — `tests/test_mcp/test_cop_server.py` — extend — add `test_validate_move_agrees_with_engine`. It compares the tool verdict to the Step-1 engine directly:
      ```python
      from src.game.board import Board
      from src.game.state import GameState
      from src.game.moves import Move, legal_moves


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
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_validate_move_agrees_with_engine -q` passes.

- [x] **E6** — `tests/test_mcp/test_cop_server.py` — extend — add `test_validate_move_rejects_offboard`:
      ```python
      async def test_validate_move_rejects_offboard():
          server = build_cop_server(_config())
          async with Client(server) as client:
              r = await client.call_tool("validate_move", {
                  "to_move": "THIEF", "cop_pos": [0, 0], "thief_pos": [0, 0],
                  "cop_barriers_left": 5, "barriers": [], "move": "NW",
              })
          assert r.data["ok"] is False
          assert r.data["reason"]
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_validate_move_rejects_offboard -q` passes.

- [x] **E7** — `tests/test_mcp/test_cop_server.py` — extend — add `test_send_message_free_text` (arbitrary natural language is accepted):
      ```python
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
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_send_message_free_text -q` passes.

- [x] **E8** — `tests/test_mcp/test_cop_server.py` — extend — add `test_send_message_schema_has_no_coords` (the tool exposes only the opaque `envelope` parameter — no coordinate fields):
      ```python
      async def test_send_message_schema_has_no_coords():
          server = build_cop_server(_config())
          async with Client(server) as client:
              tool_list = await client.list_tools()
          send = next(t for t in tool_list if t.name == "send_message")
          props = set(send.inputSchema.get("properties", {}).keys())
          assert props == {"envelope"}
          forbidden = {"row", "col", "x", "y", "pos", "position"}
          assert not (props & forbidden)
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_send_message_schema_has_no_coords -q` passes.

- [x] **E9** — `tests/test_mcp/test_cop_server.py` — extend — add `test_place_barrier_cop`:
      ```python
      async def test_place_barrier_cop():
          server = build_cop_server(_config())
          async with Client(server) as client:
              ok = await client.call_tool("place_barrier", {"pos": [2, 2], "cop_barriers_left": 5, "barriers": []})
              dup = await client.call_tool("place_barrier", {"pos": [2, 2], "cop_barriers_left": 5, "barriers": [[2, 2]]})
              none_left = await client.call_tool("place_barrier", {"pos": [2, 2], "cop_barriers_left": 0, "barriers": []})
          assert ok.data["ok"] is True
          assert dup.data["ok"] is False
          assert none_left.data["ok"] is False
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_place_barrier_cop -q` passes.

- [x] **E10** — `tests/test_mcp/test_cop_server.py` — extend — add `test_cop_has_place_barrier`:
      ```python
      async def test_cop_has_place_barrier():
          server = build_cop_server(_config())
          async with Client(server) as client:
              names = {t.name for t in await client.list_tools()}
          assert "place_barrier" in names
          assert {"ping", "validate_location", "validate_move", "send_message"} <= names
      ```
      **Check:** `pytest tests/test_mcp/test_cop_server.py::test_cop_has_place_barrier -q` passes.

- [x] **E11** — `tests/test_mcp/test_thief_server.py` — create — header + fixture (mirror of the Cop test file):
      ```python
      from fastmcp import Client
      from src.game.config import load_config
      from src.mcp_servers.thief_server import build_thief_server


      def _config():
          return load_config("config.yaml")
      ```
      **Check:** `python -c "import ast; ast.parse(open('tests/test_mcp/test_thief_server.py').read()); print('ok')"` prints `ok`.

- [x] **E12** — `tests/test_mcp/test_thief_server.py` — extend — add `test_ping_thief`:
      ```python
      async def test_ping_thief():
          server = build_thief_server(_config())
          async with Client(server) as client:
              result = await client.call_tool("ping", {})
          assert result.data["ok"] is True
          assert result.data["server"] == "thief"
      ```
      **Check:** `pytest tests/test_mcp/test_thief_server.py::test_ping_thief -q` passes.

- [x] **E13** — `tests/test_mcp/test_thief_server.py` — extend — add `test_thief_validate_location_and_message`:
      ```python
      async def test_thief_validate_location_and_message():
          server = build_thief_server(_config())
          async with Client(server) as client:
              loc = await client.call_tool("validate_location", {"pos": [1, 1], "barriers": []})
              msg = await client.call_tool("send_message", {"envelope": {
                  "from": "thief", "turn": 2, "ts": "t", "text": "you'll never catch me — I'm heading nowhere near you",
              }})
          assert loc.data["ok"] is True
          assert msg.data["ok"] is True
      ```
      **Check:** `pytest tests/test_mcp/test_thief_server.py::test_thief_validate_location_and_message -q` passes.

- [x] **E14** — `tests/test_mcp/test_thief_server.py` — extend — add `test_asymmetry_place_barrier` (the **deliberate, tested design point**: Thief has no `place_barrier`):
      ```python
      async def test_asymmetry_place_barrier():
          server = build_thief_server(_config())
          async with Client(server) as client:
              names = {t.name for t in await client.list_tools()}
          assert "place_barrier" not in names
          assert {"ping", "validate_location", "validate_move", "send_message"} <= names
      ```
      **Check:** `pytest tests/test_mcp/test_thief_server.py::test_asymmetry_place_barrier -q` passes.

- [x] **E15** — `tests/test_mcp/test_resizable.py` — create — prove bounds come from `Config.grid_size` by overriding it to 3×3:
      ```python
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
      ```
      **Check:** `pytest tests/test_mcp/test_resizable.py::test_resizable_3x3 -q` passes.

## Phase F — full verification

- [x] **F1** — full suite — run everything; Step-1 and Step-2 must both be green.
      **Check:** `pytest -q` passes (all Step-1 tests + all `tests/test_mcp/` tests).

- [x] **F2** — no hard-coding — confirm no port or grid literal leaked into the server layer.
      **Check:** `grep -rnE "\b(8001|8002|127\.0\.0\.1|\[5, 5\]|25)\b" src/mcp_servers` returns **nothing** (all such values come from `config.yaml`/`Config`).

- [x] **F3** — servers launch — start each server briefly to confirm it binds its config port without error.
      **Check (PowerShell):** run `python -m src.mcp_servers.cop_server` in one terminal — it should print FastMCP startup/banner and bind `127.0.0.1:8001` with no traceback; stop it with Ctrl-C. Repeat for `python -m src.mcp_servers.thief_server` (binds `8002`). (If you cannot run a blocking server in this environment, instead confirm `python -c "from src.game.config import load_config; from src.mcp_servers.cop_server import build_cop_server; from src.mcp_servers.thief_server import build_thief_server; c=load_config('config.yaml'); build_cop_server(c); build_thief_server(c); print('both build ok')"` prints `both build ok` — the build path is what the unit tests already exercise.)

---

## Definition of Done
- [x] Every box above is ticked and its Check passed.
- [x] All PRD acceptance criteria hold (`PRD_step2_mcp_infra.md` §7).
- [x] No hard-coded ports or game parameters anywhere in `src/mcp_servers/` (F2 clean).
- [x] Both servers build and (F3) launch on their config-driven ports; every tool on every server has a passing in-memory-`Client` test.
- [x] Asymmetry holds: `place_barrier` on Cop, absent on Thief.
- [x] Update `docs/_system/ROADMAP.md`: set step 2 to ✅ and append a progress-log line.
