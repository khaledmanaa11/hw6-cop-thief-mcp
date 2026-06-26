# PLAN — Step 2: Basic MCP infrastructure

- **Status:** triplet-built
- **Source:** `DECISION_step2_mcp_infra.md`, `PRD_step2_mcp_infra.md`

## 1. Architecture overview
Two **stateless** FastMCP servers sit in front of the Step-1 engine. Each server registers tools that are **thin adapters**: they receive everything they need as call arguments, build throwaway `Board`/`GameState` objects, ask the Step-1 engine the question (in-bounds? blocked? legal move?), and re-shape the answer into a `{ok, reason}` dict. No server holds game state — the live `GameState` will be owned by the Step-3 referee/client.

```
            in-memory Client (tests)        future: orchestrator over HTTP
                       │                                  │
                       ▼                                  ▼
        ┌──────────────────────────┐      ┌──────────────────────────┐
        │  cop_server (FastMCP)     │      │  thief_server (FastMCP)   │
        │  ping/validate_location/  │      │  ping/validate_location/  │
        │  validate_move/send_msg/  │      │  validate_move/send_msg   │
        │  place_barrier ★Cop only  │      │  (NO place_barrier)       │
        └─────────────┬─────────────┘      └─────────────┬─────────────┘
                      │   both call the SAME adapters     │
                      └───────────────┬───────────────────┘
                                      ▼
                       src/mcp_servers/tools.py  (pure adapters)
                                      │ delegates to
                                      ▼
                  src/game/{board,state,moves,config}.py  (Step-1 engine)
```

The shared adapter functions live in `tools.py` and return plain dicts. Each server file wraps the relevant adapters with `@mcp.tool` so the **same logic** is registered on both servers (and the Cop server additionally registers `place_barrier`). This guarantees the two servers behave identically for shared tools and differ **only** in the deliberate asymmetry.

## 2. File / module layout
```
src/mcp_servers/__init__.py        (new)   — make src.mcp_servers an importable package
src/mcp_servers/tools.py           (new)   — pure adapter funcs over the Step-1 engine; return {ok, reason, ...}
src/mcp_servers/cop_server.py      (new)   — build_cop_server(config)->FastMCP (shared tools + place_barrier) + __main__ launcher
src/mcp_servers/thief_server.py    (new)   — build_thief_server(config)->FastMCP (shared tools only) + __main__ launcher
src/game/config.py                 (edit)  — add ServerEndpoint/ServersConfig dataclasses; parse a `servers:` block (default None, backward-compatible)
config.yaml                        (edit)  — add the `servers:` block (cop/thief host+port)
requirements.txt                   (edit)  — add `fastmcp` and `pytest-asyncio`
pyproject.toml                     (edit)  — add `asyncio_mode = "auto"` so async tests run without per-test markers
tests/test_mcp/__init__.py         (new)   — make the test package importable
tests/test_mcp/test_cop_server.py  (new)   — in-memory Client tests for every Cop tool
tests/test_mcp/test_thief_server.py(new)   — in-memory Client tests for every Thief tool + asymmetry
tests/test_mcp/test_resizable.py   (new)   — tools derive bounds from Config.grid_size (3×3 run)
```

## 3. Data model / key structures
- **Result shape (every tool):** `{ "ok": bool, "reason": str }` — `reason` is a non-empty human-readable string. `ping` adds `"server": "cop"|"thief"`.
- **Message envelope (input to `send_message`):** `{ "from": str, "turn": int, "ts": str, "text": str }` — `text` is opaque free natural language; **no coordinate fields**. (`from` is a Python keyword, so it is only ever a *dict key*, never a parameter name — the tool parameter is the whole `envelope` dict.)
- **`ServerEndpoint`** (new, `src/game/config.py`) — `host: str`, `port: int`.
- **`ServersConfig`** (new) — `cop: ServerEndpoint`, `thief: ServerEndpoint`.
- **`Config.servers`** (new field, default `None`) — a `ServersConfig | None`; populated by `load_config` when a `servers:` block is present. Default `None` keeps every existing positional `Config(...)` construction in the Step-1 tests valid.
- **Engine types reused (unchanged):** `Board(rows, cols)` with `.barriers: set[tuple[int,int]]`, `.in_bounds(pos)`, `.is_blocked(pos)`; `GameState(cop_pos, thief_pos, to_move, moves_used, cop_barriers_left, board)`; `Move` enum (`N S E W NE NW SE SW PLACE_BARRIER`); `legal_moves(state) -> list[Move]`.

## 4. Component design

### `src/mcp_servers/tools.py` — pure adapters (no FastMCP imports)
- **Responsibility:** translate raw call arguments into Step-1 engine questions and return `{ok, reason}` dicts. Importable and unit-testable on their own; contains **no** game-rule logic of its own beyond shaping.
- **Helpers:**
  - `def _board_with_barriers(config, barriers) -> Board:` — builds `Board(*config.grid_size)` and adds every `tuple(b)` in `barriers` to `board.barriers`.
- **Adapter functions:**
  - `def ping_result(server_name: str) -> dict:` → `{"ok": True, "server": server_name, "reason": f"{server_name} server alive"}`.
  - `def validate_location_result(pos, barriers, config) -> dict:` → off-board ⇒ `{ok:False, reason:"off-board: …"}`; barrier ⇒ `{ok:False, reason:"blocked: barrier at …"}`; else `{ok:True, reason:"clear: …"}`.
  - `def validate_move_result(to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move, config) -> dict:` — build a `GameState`, resolve `Move[move]` (unknown name ⇒ `{ok:False}`), return `ok` = membership in `legal_moves(state)` with a descriptive reason.
  - `def send_message_result(envelope) -> dict:` — require keys `from/turn/ts/text`; `text` must be `str`; ack with `{ok:True, reason:"message accepted from <from> at turn <turn>"}`.
  - `def place_barrier_result(pos, cop_barriers_left, barriers, config) -> dict:` — `cop_barriers_left<=0` ⇒ `{ok:False,"no barriers left"}`; off-board ⇒ `{ok:False}`; already a barrier ⇒ `{ok:False}`; else `{ok:True, reason:"valid barrier site: …"}`. **Validation only — never calls `board.place_barrier` for real, never mutates anything persistent.**

### `src/mcp_servers/cop_server.py`
- **Responsibility:** build the Cop FastMCP instance and launch it.
- `def build_cop_server(config) -> FastMCP:` — create `FastMCP("cop")`; register `ping`, `validate_location`, `validate_move`, `send_message` (delegating to `tools.*` with `server_name="cop"`), **plus** `place_barrier`. Return the instance.
- `__main__`: `config = load_config("config.yaml")`; `mcp = build_cop_server(config)`; `mcp.run(transport="http", host=config.servers.cop.host, port=config.servers.cop.port)`.

### `src/mcp_servers/thief_server.py`
- Same as Cop **minus `place_barrier`**; `FastMCP("thief")`; `server_name="thief"`; `__main__` uses `config.servers.thief.{host,port}`.

### `src/game/config.py` (edit)
- Add `ServerEndpoint` and `ServersConfig` dataclasses; add `servers: ServersConfig | None = None` as the **last** `Config` field (default keeps positional construction working).
- In `load_config`, if `"servers"` in data, parse `data["servers"]["cop"|"thief"]["host"|"port"]`, validate `1 <= port <= 65535` and non-empty host, build `ServersConfig`; else leave `None`.

## 5. Control flow / sequences
**One `validate_move` call (in-memory test):**
1. Test enters `async with Client(cop_server) as client:`.
2. `await client.call_tool("validate_move", {"to_move":"THIEF","cop_pos":[0,0],"thief_pos":[4,4],"cop_barriers_left":5,"barriers":[],"move":"NW"})`.
3. Tool body calls `tools.validate_move_result(...)` → builds `Board(5,5)`, `GameState(...)`, computes `legal_moves(state)`, checks `Move["NW"] in legal_moves`.
4. Returns `{"ok": True, "reason": "legal: NW for THIEF"}`.
5. FastMCP serializes; client receives `result`; test asserts `result.data["ok"] is True` and `result.data["reason"]` is non-empty.

**Server launch (`python -m src.mcp_servers.cop_server`):** load config → build server → `mcp.run(transport="http", host=…, port=…)` binds `127.0.0.1:8001` and blocks serving.

## 6. Config additions
| Key | Default | Used by |
|-----|---------|---------|
| `servers.cop.host` | `127.0.0.1` | `cop_server.__main__` |
| `servers.cop.port` | `8001` | `cop_server.__main__` |
| `servers.thief.host` | `127.0.0.1` | `thief_server.__main__` |
| `servers.thief.port` | `8002` | `thief_server.__main__` |

## 7. Test strategy
- **Unit (adapters):** `tools.*_result` functions can be asserted directly (no async) for fast, transport-free checks.
- **Integration (in-memory Client):** for each server, `async with Client(build_*_server(config)) as client:` then `call_tool`/`list_tools`. Uses `pytest-asyncio` in `asyncio_mode = "auto"` (no per-test marker needed).
- **Engine-agreement:** pick a move the Step-1 `legal_moves` accepts and one it rejects (off-board / into a barrier) and assert `validate_move` matches.
- **Asymmetry:** `await client.list_tools()` on the Thief server → assert `"place_barrier"` **not** in the tool names; on the Cop server → assert it **is**.
- **Schema / free-text:** assert `send_message`'s input schema exposes only the `envelope` parameter (no `row`/`col`/`x`/`y`/`pos`), and that a long free-text `text` is accepted.
- **Resizability:** load config, override `grid_size` to `(3,3)`, build the server, and assert an off-board location for 3×3 (e.g. `(3,3)`) is rejected while `(2,2)` is clear.
- **Regression:** the whole `pytest -q` (Step-1 + Step-2) stays green.

## 8. Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Wrong `fastmcp` run/transport signature | Low | Verified vs live v3.2.4 docs: `mcp.run(transport="http", host=…, port=…)`, in-memory `Client(server)`, `result.data`. |
| Async tests not collected | Medium | Add `pytest-asyncio` + `asyncio_mode = "auto"` in `pyproject.toml`. |
| Adding `Config.servers` breaks Step-1 tests | Medium | New field is **last** with default `None`; parsing is conditional on a `servers:` block. |
| Mutable-default / keyword pitfalls (`from`, `barriers=[]`) | Low | `envelope` is a dict (so `from` is only a key); `barriers` is a required list arg in tool signatures (no mutable default). |
| Accidentally mutating state in `place_barrier` | Low | Adapter only inspects a throwaway `Board`; never calls `board.place_barrier`. |
| Tool returns not structured as dict | Low | Every tool is annotated `-> dict`; client reads `result.data` (FastMCP hydrates the dict). |

## 9. Work breakdown (macro order)
1. **Deps & config** — `requirements.txt`, `pyproject.toml`, `config.yaml` `servers:` block, `Config` parsing.
2. **Adapters** — `src/mcp_servers/tools.py` (pure functions + helper).
3. **Servers** — `cop_server.py`, `thief_server.py` (builders + `__main__`).
4. **Tests** — per-tool in-memory tests, asymmetry, schema, resizability.
5. **Verify** — full suite green, no hard-coded literals, both servers launch.
