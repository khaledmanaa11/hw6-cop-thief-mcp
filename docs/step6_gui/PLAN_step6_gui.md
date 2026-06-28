# PLAN - Step 6: Graphical User Interface

- **Status:** triplet-built
- **Source:** `DECISION_step6_gui.md`, `SDK_REFERENCE_fastapi.md`, `PRD_step6_gui.md`

## 1. Architecture overview
Step 6 adds a presentation package that sits beside, not inside, the game/orchestrator runtime. The required path is replay-first:

```text
runs/*.jsonl or tests/test_gui/fixtures/*.jsonl
        |
        v
src/gui/replay.py
  read JSONL -> raw records -> cumulative Frame list
  conversation, board, ghosts, fog, telemetry, score/status
        |
        v
src/gui/app.py
  FastAPI routes: /, /api/runs, /api/runs/{name}, /static/*
        |
        v
src/gui/static/
  index.html + app.js + style.css
  canvas renderer; no game/replay data shaping
```

The replay path must not import or mutate the engine, MCP servers, strategy, agents, or orchestrator loop. It consumes the Step 5 JSONL record shape read-only. `app.py` can import `load_config` only for CLI startup/config, and `replay.py` can import only standard-library modules.

Important live-contract correction: the current JSONL record does not have a top-level `grid`; grid dimensions are present in `obs.COP.grid` and `obs.THIEF.grid`. `replay.py` should prefer `obs.*.grid`, tolerate a future/fixture top-level `grid`, then fall back to inferring bounds only for malformed/old logs.

## 2. File / module layout
```
src/gui/__init__.py                         (new)   - package marker and public version/export
src/gui/__main__.py                         (new)   - supports `python -m src.gui`
src/gui/replay.py                           (new)   - pure JSONL-to-Run/Frame shaping; no FastAPI, no engine imports
src/gui/app.py                              (new)   - FastAPI app factory, routes, static mount, uvicorn startup
src/gui/static/index.html                   (new)   - app shell: canvas, run selector, controls, panels
src/gui/static/app.js                       (new)   - thin renderer/fetch/controller only
src/gui/static/style.css                    (new)   - responsive layout and canvas/panel styling
src/game/config.py                          (edit)  - add trailing-optional `gui` dict default/validation
config.yaml                                 (edit)  - append `gui:` block
pyproject.toml / uv.lock                    (edit)  - dependency state from `uv add` pins
tests/test_gui/__init__.py                  (new)   - package marker
tests/test_gui/fixtures/replay_3x3.jsonl    (new)   - committed small run proving resizability and privacy
tests/test_gui/fixtures/replay_5x5.jsonl    (new)   - committed small run proving non-3x3 path
tests/test_gui/test_replay.py               (new)   - unit tests for `replay.py`
tests/test_gui/test_app.py                  (new)   - FastAPI `TestClient` route tests
tests/test_gui/test_static_guards.py        (new)   - line-count, no-hard-code, no-tier-crossing guards
docs/step6_gui/gui_replay_screenshot.png    (new)   - README-ready visual proof artifact after implementation
```

Optional stretch only:

```
src/gui/live.py                             (optional new) - SSE helpers if live mode is attempted
tests/test_gui/test_live_optional.py        (optional new) - graceful-unavailable/live stream tests
```

## 3. Data model / key structures
- `Frame` - `dict[str, Any]` with fields:
  `turn: int`, `side: str`, `move: str | None`,
  `board: {"grid": [rows, cols], "cop_pos": [r, c], "thief_pos": [r, c], "barriers": [[r, c], ...]}`,
  `message: dict | None`,
  `conversation: list[dict]`,
  `beliefs: {"COP": {"guess": [r, c] | None, "error": int | None}, "THIEF": {...}}`,
  `fog: {"COP": dict, "THIEF": dict}`,
  `score: dict`,
  `moves_left: int | None`,
  `llm: dict`,
  `confidence: str | None`,
  `intent: str | None`.
- `Run` - `dict[str, Any]` with fields:
  `name: str`, `grid: [rows, cols]`, `frames: list[Frame]`, `final_score: dict`, `telemetry_summary: dict`.
- `RunMeta` - `dict[str, Any]` with fields:
  `name: str`, `mtime: float`, `turns: int`, `grid: [rows, cols] | None`.
- `Conversation item` - public only:
  `{"from": str, "turn": int, "ts": str | None, "text": str, "current": bool}`.
  It must not include `reasoning`, `belief`, `confidence`, `intent`, or `llm`.
- `Score/status` - display object:
  `{"cop": int, "thief": int, "available": bool, "note": str | None}`.
  If records include `score`, `cop_score`/`thief_score`, or `series_score`, use them. If not, keep scores at zero and set `available: false`; do not invent official point totals from hard-coded scoring values.

## 4. Component design

### `src/gui/replay.py`
- **Responsibility:** pure, deterministic transform from JSONL records into render-ready data. No FastAPI imports, no engine imports, no file writes.
- **Key functions:**
  - `def load_run(path: str | Path) -> Run:` parse JSONL and return `Run`; empty files return an empty run with grid `[0, 0]`.
  - `def list_runs(run_dir: str | Path) -> list[RunMeta]:` list readable `*.jsonl` files newest-first by mtime; unreadable files get `turns: 0`, `grid: None`.
  - `def to_frames(records: list[dict[str, Any]]) -> list[Frame]:` fold raw records into cumulative frames; this is the highest-coverage function.
  - `def ghost_marker(record: dict[str, Any]) -> dict[str, Any]:` return `{"guess": action.belief, "error": action.belief_error}`.
  - `def fog_view(record: dict[str, Any], side: str) -> dict[str, Any]:` return a shallow JSON-safe copy of `record["obs"][side]` or `{}`.
  - `def running_score(frames: list[Frame]) -> dict[str, Any]:` return the final score/status object from the last frame, not hard-coded scoring math.
- **Edge cases:**
  - Missing `action`, `obs`, `ground_truth`, `llm`, or score fields must not crash.
  - `reasoning` can remain in raw records but must never enter `conversation`.
  - Grid must come from `obs.*.grid` when available; no 5x5 literal in `src/gui/`.

### `src/gui/app.py`
- **Responsibility:** route wiring and CLI startup only.
- **Key functions:**
  - `def create_app(config) -> FastAPI:` build app, compute `run_dir = Path(config.gui["run_dir"])`, mount static files, define routes.
  - `def _safe_run_path(run_dir: Path, name: str) -> Path | None:` prevent path traversal; accept only basename `.jsonl` files within `run_dir`.
  - `def main() -> None:` load `config.yaml`, create app, call `uvicorn.run(app, host=config.gui["host"], port=config.gui["port"])`.
- **Routes:**
  - `GET /` returns `FileResponse(static_dir / "index.html")`.
  - `GET /api/runs` returns `{"runs": list_runs(run_dir)}`.
  - `GET /api/runs/{name}` returns `load_run(path)` or `HTTPException(404)`.
  - `app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")`.

### `src/gui/static/index.html`
- **Responsibility:** static shell with a canvas, run selector, scrub/play controls, fog toggle, conversation panel, telemetry/status panel.
- **Constraints:** no inline game logic; load `/static/app.js` and `/static/style.css`; keep the file at or below 150 lines.

### `src/gui/static/app.js`
- **Responsibility:** fetch `/api/runs`, fetch selected run JSON, hold `frames` and `currentIndex`, draw the current frame, and update DOM panels.
- **Constraints:** no replay folding, no belief error math, no observation leakage decisions, no score computation. All such data must already be in the frame.

### `src/gui/static/style.css`
- **Responsibility:** compact, utilitarian replay layout with a responsive board and panels. The UI should be a tool, not a landing page.
- **Constraints:** no one-note palette, no overlapping text, fixed-size controls, canvas scales by container while preserving board aspect.

### `src/game/config.py`
- **Responsibility:** add trailing-optional GUI config without breaking positional `Config(...)` construction.
- **Key behavior:** add `gui: dict | None = None` at the end of `Config`; merge `_DEFAULT_GUI`; validate non-empty host, port in `1..65535`; default `gui.run_dir` to `output_run_dir`.

## 5. Control flow / sequences
1. Developer runs `python -m src.gui`.
2. `src/gui/__main__.py` calls `src.gui.app.main()`.
3. `main()` loads `config.yaml`; `load_config` provides `config.gui`.
4. `create_app(config)` computes `run_dir` from `config.gui["run_dir"]`, mounts `src/gui/static`, and wires routes.
5. Browser requests `/`; FastAPI returns `index.html`.
6. `app.js` requests `/api/runs`; backend returns JSONL run metadata from `list_runs`.
7. User selects a run; `app.js` requests `/api/runs/{name}`.
8. Backend validates the filename, calls `load_run`, and returns a `Run`.
9. `app.js` renders the current `Frame` only. Previous/next/play/scrub change the index and redraw.
10. Fog toggle changes which already-provided `frame.fog[side]` projection is visualized; JS does not compute hidden information.

## 6. Config additions
| Key | Default | Used by |
|-----|---------|---------|
| `gui.host` | `"127.0.0.1"` | `src.gui.app.main` / `uvicorn.run` |
| `gui.port` | `8000` | `src.gui.app.main` / `uvicorn.run` |
| `gui.run_dir` | `output.run_dir` (normally `"runs"`) | `create_app`, `/api/runs`, `/api/runs/{name}` |

`gui:` is trailing-optional. If the YAML block is absent, `load_config` still returns a valid `config.gui` dict.

## 7. Test strategy
- **Unit:** `tests/test_gui/test_replay.py` covers JSONL parsing, `to_frames`, `ghost_marker`, `fog_view`, `running_score`, conversation privacy, 3x3/5x5 resizability, missing optional fields, and `list_runs`.
- **Integration:** `tests/test_gui/test_app.py` uses FastAPI `TestClient` to test `/`, `/api/runs`, `/api/runs/{name}`, 404/path traversal behavior, and static mount availability without opening a socket.
- **Static guards:** `tests/test_gui/test_static_guards.py` checks every `src/gui/` file is at most 150 lines, `src/gui/` does not import forbidden tiers for replay, no hard-coded grid/port/model/API-key strings appear, and `reasoning` is not referenced by frontend rendering.
- **Sanity-grid escalation:** committed fixture tests prove 3x3 and 5x5. Existing game/strategy/orchestrator tests continue covering wider behavior; Step 6 must not modify those tiers.
- **Manual visual:** run `python -m src.gui`, open the configured URL, load the 3x3 fixture, capture `docs/step6_gui/gui_replay_screenshot.png`.

## 8. Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Per-ply JSONL lacks official series point totals | Medium | Expose score/status as available only when score fields exist; never hard-code scoring in `src/gui/`; document unavailable state |
| JS grows into untested data shaping | Medium | Frame contract contains all render data; tests assert Python shaping; static guard scans `app.js` for forbidden fields like `reasoning` |
| Path traversal in run API | Medium | `_safe_run_path` accepts only basename `.jsonl` under configured run dir; endpoint tests cover rejection |
| FastAPI/TestClient API drift | Low | `SDK_REFERENCE_fastapi.md` pins verified current versions and code shape |
| File-size gate fails | Medium | Keep `replay.py` pure, `app.py` routes-only, and split only optional live code into `live.py` |
| Replay imports runtime tiers accidentally | Medium | Static guard blocks imports from `src.game`, `src.mcp_servers`, `src.orchestrator`, `src.strategy`, and `src.agents` in `src/gui/replay.py` |
| Real old logs miss optional Step 5 fields | High | `to_frames` uses `.get()` throughout and returns empty/default display objects |
| Browser rendering cannot be tested by pytest | Medium | Put all logic in Python; JS is dumb renderer; manual screenshot covers visual artifact |

## 9. Work breakdown (macro order)
1. Add FastAPI dependencies and trailing-optional GUI config.
2. Implement `src/gui/replay.py` with pure data shapes and helper functions.
3. Commit 3x3 and 5x5 JSONL fixtures matching the real Step 5 record contract.
4. Add replay unit tests and privacy/resizability coverage.
5. Implement `src/gui/app.py`, `src/gui/__main__.py`, and endpoint tests via `TestClient`.
6. Implement static HTML/canvas/CSS frontend as a thin renderer.
7. Add static guard tests, run ruff/coverage/full suite, and capture README screenshot.
8. Optionally add SSE live streaming as a clearly cuttable stretch.
