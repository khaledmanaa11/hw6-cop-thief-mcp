# TODO - Step 6: Graphical User Interface

> Implements `PRD_step6_gui.md` + `PLAN_step6_gui.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**
> This is the Developer-session checklist. The Builder session that wrote this file must not edit source code.

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never hard-code** GUI ports, run directories, model strings, API keys, or grid sizes in `src/gui/`.
4. Do not assume a 5x5 grid. Board dimensions come from each frame's `board.grid`, which comes from JSONL `obs.*.grid`.
5. Replay mode is presentation only: do not import or modify the engine, MCP servers, agents, strategy, or orchestrator runtime loop for `src/gui/replay.py`.
6. Keep all data shaping in Python (`replay.py`) and all route behavior in Python (`app.py`). JavaScript only renders frames it receives.
7. `reasoning` is private. It may exist in raw JSONL but must never enter `Frame.conversation` or any frontend conversation panel.
8. Use `uv` for dependencies. Do not hand-edit `requirements.txt` for Step 6.
9. Keep every file under `src/gui/` at or below 150 lines.
10. Run commands from the repository root, the folder containing `config.yaml`.

## Conventions
- Language/runtime: Python 3.11+ using `uv`, pytest, FastAPI, Uvicorn.
- Verified web pins: `fastapi==0.138.1`, `uvicorn[standard]==0.49.0`, `httpx==0.28.1`.
- Source root: `src/` · Tests: `tests/`.
- Type aliases in `replay.py`: `Frame = dict[str, Any]`, `Run = dict[str, Any]`, `RunMeta = dict[str, Any]`.
- Role spelling in records: uppercase `"COP"` and `"THIEF"`.
- Each box format: **ID · file · action · detail · Check.**

---

## Phase A - dependencies, config, and package scaffolding

- [ ] **A1** - `pyproject.toml` / `uv.lock` - update via `uv` - add the verified FastAPI stack and test tooling. Run:
  ```powershell
  uv add fastapi==0.138.1 "uvicorn[standard]==0.49.0" httpx==0.28.1
  uv add --dev ruff pytest-cov
  ```
  Do not edit `requirements.txt`.
  **Check:** `uv run python -c "import importlib.metadata as m; print(m.version('fastapi'), m.version('uvicorn'), m.version('httpx'))"` prints `0.138.1 0.49.0 0.28.1`.

- [ ] **A2** - `src/game/config.py` - edit - add trailing-optional GUI config without moving existing dataclass fields. Add near the other defaults:
  ```python
  _DEFAULT_GUI = {"host": "127.0.0.1", "port": 8000}
  ```
  Add `gui: dict | None = None` at the end of `Config`. In `load_config`, after `output_run_dir` is computed, merge:
  ```python
  gui = _merged_defaults(_DEFAULT_GUI, data.get("gui"))
  gui["run_dir"] = gui.get("run_dir") or output_run_dir
  if not gui["host"]:
      raise ValueError("gui.host must be non-empty")
  gui["port"] = int(gui["port"])
  if not (1 <= gui["port"] <= 65535):
      raise ValueError(f"gui.port out of range: {gui['port']}")
  if not gui["run_dir"]:
      raise ValueError("gui.run_dir must be non-empty")
  ```
  Pass `gui=gui` in the returned `Config`.
  **Check:** `uv run python -c "from src.game.config import load_config; c=load_config('config.yaml'); print(c.gui['host'], c.gui['port'], c.gui['run_dir'])"` prints valid values after A3.

- [ ] **A3** - `config.yaml` - edit - append the trailing-optional GUI block without changing existing keys:
  ```yaml
  gui:
    host: "127.0.0.1"
    port: 8000
    run_dir: "runs"
  ```
  **Check:** `uv run python -c "from src.game.config import load_config; c=load_config('config.yaml'); print(c.gui)"` prints a dict with `host`, `port`, and `run_dir`.

- [ ] **A4** - `src/gui/__init__.py` - create - add a small package marker and public version:
  ```python
  """Replay GUI for HW6 Cop-and-Thief JSONL runs."""

  __all__ = ["__version__"]
  __version__ = "0.1.0"
  ```
  **Check:** `uv run python -c "import src.gui; print(src.gui.__version__)"` prints `0.1.0`.

- [ ] **A5** - `src/gui/__main__.py` - create - support `python -m src.gui`:
  ```python
  from src.gui.app import main


  if __name__ == "__main__":
      main()
  ```
  This will import cleanly after `app.py` exists in Phase E.
  **Check:** `uv run python -m py_compile src/gui/__main__.py` succeeds after Phase E.

- [ ] **A6** - `tests/test_gui/__init__.py` - create - empty package marker. Also create the directory `tests/test_gui/fixtures/`.
  **Check:** `uv run python -c "import tests.test_gui; print('ok')"` prints `ok`.

---

## Phase B - `src/gui/replay.py` core data shaping

- [ ] **B1** - `src/gui/replay.py` - create - add imports, aliases, and JSON-safe helper. Keep this module standard-library only:
  ```python
  from __future__ import annotations

  import json
  from pathlib import Path
  from typing import Any

  Frame = dict[str, Any]
  Run = dict[str, Any]
  RunMeta = dict[str, Any]

  SIDES = ("COP", "THIEF")


  def _json_copy(value: Any) -> Any:
      return json.loads(json.dumps(value))
  ```
  **Check:** `uv run python -m py_compile src/gui/replay.py` succeeds.

- [ ] **B2** - `src/gui/replay.py` - edit - add JSONL reading and grid helpers:
  ```python
  def _read_jsonl(path: Path) -> list[dict[str, Any]]:
      records: list[dict[str, Any]] = []
      with path.open(encoding="utf-8") as fh:
          for line_no, line in enumerate(fh, start=1):
              text = line.strip()
              if not text:
                  continue
              try:
                  records.append(json.loads(text))
              except json.JSONDecodeError as exc:
                  raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
      return records


  def _grid(record: dict[str, Any]) -> list[int]:
      for side in SIDES:
          grid = record.get("obs", {}).get(side, {}).get("grid")
          if grid:
              return list(grid)
      if record.get("grid"):
          return list(record["grid"])
      truth = record.get("ground_truth", {})
      coords = [truth.get("cop_pos"), truth.get("thief_pos"), *truth.get("barriers", [])]
      rows = max((p[0] for p in coords if p), default=-1) + 1
      cols = max((p[1] for p in coords if p), default=-1) + 1
      return [rows, cols]
  ```
  **Check:** `uv run python -m py_compile src/gui/replay.py` succeeds.

- [ ] **B3** - `src/gui/replay.py` - edit - add board, conversation, ghost, and fog helpers. These are privacy-critical:
  ```python
  def _board(record: dict[str, Any]) -> dict[str, Any]:
      truth = record.get("ground_truth", {})
      return {
          "grid": _grid(record),
          "cop_pos": truth.get("cop_pos"),
          "thief_pos": truth.get("thief_pos"),
          "barriers": truth.get("barriers", []),
      }


  def _conversation_item(message: dict[str, Any], current: bool) -> dict[str, Any]:
      return {
          "from": message.get("from"),
          "turn": message.get("turn"),
          "ts": message.get("ts"),
          "text": message.get("text", ""),
          "current": current,
      }


  def ghost_marker(record: dict[str, Any]) -> dict[str, Any]:
      action = record.get("action", {})
      return {"guess": action.get("belief"), "error": action.get("belief_error")}


  def fog_view(record: dict[str, Any], side: str) -> dict[str, Any]:
      return _json_copy(record.get("obs", {}).get(side.upper(), {}))
  ```
  Do not copy `action.reasoning` in `_conversation_item`.
  **Check:** `uv run python -c "from src.gui.replay import ghost_marker; print(ghost_marker({'action': {'belief': [1, 2], 'belief_error': 3}}))"` prints the belief and error.

- [ ] **B4** - `src/gui/replay.py` - edit - add score/status and telemetry helpers. Do not hard-code assignment scoring values:
  ```python
  def _score_from_record(record: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
      if "score" in record:
          score = dict(record["score"])
          score.setdefault("available", True)
          score.setdefault("note", None)
          return score
      if "series_score" in record:
          score = dict(record["series_score"])
          score.setdefault("available", True)
          score.setdefault("note", None)
          return score
      if "cop_score" in record or "thief_score" in record:
          return {
              "cop": record.get("cop_score", previous.get("cop", 0)),
              "thief": record.get("thief_score", previous.get("thief", 0)),
              "available": True,
              "note": None,
          }
      return dict(previous)


  def _moves_left(record: dict[str, Any]) -> int | None:
      side = record.get("side", "COP")
      obs = record.get("obs", {}).get(side) or record.get("obs", {}).get("COP", {})
      return obs.get("moves_left")


  def _telemetry_summary(frames: list[Frame]) -> dict[str, Any]:
      llm = [frame["llm"] for frame in frames if frame.get("llm")]
      return {
          "llm_calls": len(llm),
          "llm_latency_ms": sum(x.get("latency_ms", 0) for x in llm),
          "llm_input_tokens": sum(x.get("input_tokens", 0) for x in llm),
          "llm_output_tokens": sum(x.get("output_tokens", 0) for x in llm),
      }
  ```
  **Check:** `uv run python -m py_compile src/gui/replay.py` succeeds.

- [ ] **B5** - `src/gui/replay.py` - edit - add the central `to_frames` fold exactly with this behavior:
  ```python
  def to_frames(records: list[dict[str, Any]]) -> list[Frame]:
      frames: list[Frame] = []
      conversation: list[dict[str, Any]] = []
      beliefs = {
          "COP": {"guess": None, "error": None},
          "THIEF": {"guess": None, "error": None},
      }
      score = {"cop": 0, "thief": 0, "available": False, "note": "score not present in JSONL"}

      for record in records:
          side = str(record.get("side", "")).upper()
          message = record.get("message") or {}
          if message.get("text") is not None:
              conversation.append(_conversation_item(message, current=False))
          for item in conversation:
              item["current"] = False
          if conversation:
              conversation[-1]["current"] = True

          if side in beliefs:
              beliefs[side] = ghost_marker(record)
          score = _score_from_record(record, score)
          action = record.get("action", {})

          frames.append(
              {
                  "turn": record.get("turn"),
                  "side": side,
                  "move": record.get("move"),
                  "board": _board(record),
                  "message": _json_copy(message) if message else None,
                  "conversation": _json_copy(conversation),
                  "beliefs": _json_copy(beliefs),
                  "fog": {"COP": fog_view(record, "COP"), "THIEF": fog_view(record, "THIEF")},
                  "score": dict(score),
                  "moves_left": _moves_left(record),
                  "llm": _json_copy(action.get("llm", {})),
                  "confidence": action.get("confidence"),
                  "intent": action.get("intent"),
              }
          )
      return frames
  ```
  This is the main coverage target. It must not surface `action.reasoning`.
  **Check:** `uv run python -m py_compile src/gui/replay.py` succeeds.

- [ ] **B6** - `src/gui/replay.py` - edit - add public `running_score`, `load_run`, and `list_runs`:
  ```python
  def running_score(frames: list[Frame]) -> dict[str, Any]:
      if not frames:
          return {"cop": 0, "thief": 0, "available": False, "note": "empty run"}
      return dict(frames[-1]["score"])


  def load_run(path: str | Path) -> Run:
      run_path = Path(path)
      records = _read_jsonl(run_path)
      frames = to_frames(records)
      return {
          "name": run_path.name,
          "grid": frames[0]["board"]["grid"] if frames else [0, 0],
          "frames": frames,
          "final_score": running_score(frames),
          "telemetry_summary": _telemetry_summary(frames),
      }


  def list_runs(run_dir: str | Path) -> list[RunMeta]:
      root = Path(run_dir)
      metas: list[RunMeta] = []
      for path in sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
          try:
              run = load_run(path)
              metas.append({
                  "name": path.name,
                  "mtime": path.stat().st_mtime,
                  "turns": len(run["frames"]),
                  "grid": run["grid"],
              })
          except (OSError, ValueError):
              metas.append({"name": path.name, "mtime": path.stat().st_mtime, "turns": 0, "grid": None})
      return metas
  ```
  **Check:** `uv run python -c "from src.gui.replay import load_run, list_runs, to_frames; print(callable(load_run), callable(list_runs), callable(to_frames))"` prints `True True True`.

- [ ] **B7** - `src/gui/replay.py` - audit - confirm the file has no forbidden imports and stays under 150 lines. If it exceeds 150 lines, remove blank/comment-only lines or split only non-core optional code elsewhere.
  **Check:** `uv run python -c "from pathlib import Path; p=Path('src/gui/replay.py'); text=p.read_text(); bad=[b for b in ['src.game','src.mcp_servers','src.orchestrator','src.strategy','src.agents','fastapi'] if b in text]; assert not bad, bad; assert len(text.splitlines()) <= 150; print('ok')"`

- [ ] **B8** - `src/gui/replay.py` - harden - make sure empty files, missing `action`, missing `obs`, missing `ground_truth`, and missing score fields return defaults instead of crashing. Add tiny inline smoke cases if needed.
  **Check:** `uv run python -c "from src.gui.replay import to_frames; print(to_frames([{'turn':1,'side':'COP'}])[0]['score']['available'])"` prints `False`.

---

## Phase C - committed deterministic fixtures

- [ ] **C1** - `tests/test_gui/fixtures/replay_3x3.jsonl` - create - add exactly three JSONL records. They must include real Step 5 keys (`turn`, `side`, `move`, `verdict`, `message`, `action`, `obs`, `ground_truth`) plus optional `score` for the score/status test:
  ```jsonl
  {"turn":1,"side":"COP","move":"E","verdict":{"ok":true,"reason":"legal"},"message":{"from":"COP","turn":1,"ts":"2026-06-27T00:00:01+00:00","text":"I am closing the west edge."},"action":{"message":"I am closing the west edge.","belief":[2,2],"belief_error":0,"confidence":"medium","intent":"probe","reasoning":"SECRET_REASONING_DO_NOT_SHOW","llm":{"provider":"fake","latency_ms":10,"input_tokens":5,"output_tokens":7}},"obs":{"COP":{"mode":"noisy","role":"COP","self":[0,1],"grid":[3,3],"barriers":[],"moves_used":1,"moves_left":4,"max_moves":5,"sees_opponent":false,"opponent_pos":null,"opponent_hint":"southeast","last_msg":null,"inbox":[]},"THIEF":{"mode":"blind","role":"THIEF","self":[2,2],"grid":[3,3],"barriers":[],"moves_used":1,"moves_left":4,"max_moves":5,"sees_opponent":false,"opponent_pos":null,"opponent_hint":"unseen","last_msg":"I am closing the west edge.","inbox":[{"from":"COP","turn":1,"ts":"2026-06-27T00:00:01+00:00","text":"I am closing the west edge."}]}},"ground_truth":{"cop_pos":[0,1],"thief_pos":[2,2],"barriers":[],"moves_used":1},"score":{"cop":0,"thief":0}}
  {"turn":2,"side":"THIEF","move":"NW","verdict":{"ok":true,"reason":"legal"},"message":{"from":"THIEF","turn":2,"ts":"2026-06-27T00:00:02+00:00","text":"You are chasing old footprints."},"action":{"message":"You are chasing old footprints.","belief":[0,1],"belief_error":0,"confidence":"high","intent":"deceive","reasoning":"SECRET_REASONING_DO_NOT_SHOW","llm":{"provider":"fake","latency_ms":11,"input_tokens":6,"output_tokens":8}},"obs":{"COP":{"mode":"noisy","role":"COP","self":[0,1],"grid":[3,3],"barriers":[],"moves_used":2,"moves_left":3,"max_moves":5,"sees_opponent":true,"opponent_pos":[1,1],"opponent_hint":"exact","last_msg":"You are chasing old footprints.","inbox":[{"from":"THIEF","turn":2,"ts":"2026-06-27T00:00:02+00:00","text":"You are chasing old footprints."}]},"THIEF":{"mode":"noisy","role":"THIEF","self":[1,1],"grid":[3,3],"barriers":[],"moves_used":2,"moves_left":3,"max_moves":5,"sees_opponent":true,"opponent_pos":[0,1],"opponent_hint":"exact","last_msg":"I am closing the west edge.","inbox":[{"from":"COP","turn":1,"ts":"2026-06-27T00:00:01+00:00","text":"I am closing the west edge."}]}},"ground_truth":{"cop_pos":[0,1],"thief_pos":[1,1],"barriers":[],"moves_used":2},"score":{"cop":0,"thief":0}}
  {"turn":3,"side":"COP","move":"S","verdict":{"ok":true,"reason":"legal"},"message":{"from":"COP","turn":3,"ts":"2026-06-27T00:00:03+00:00","text":"Caught you."},"action":{"message":"Caught you.","belief":[1,1],"belief_error":0,"confidence":"high","intent":"trap","reasoning":"SECRET_REASONING_DO_NOT_SHOW","llm":{"provider":"fake","latency_ms":12,"input_tokens":7,"output_tokens":3}},"obs":{"COP":{"mode":"full","role":"COP","self":[1,1],"grid":[3,3],"barriers":[],"moves_used":3,"moves_left":2,"max_moves":5,"sees_opponent":true,"opponent_pos":[1,1],"opponent_hint":"exact","last_msg":"You are chasing old footprints.","inbox":[{"from":"THIEF","turn":2,"ts":"2026-06-27T00:00:02+00:00","text":"You are chasing old footprints."}]},"THIEF":{"mode":"full","role":"THIEF","self":[1,1],"grid":[3,3],"barriers":[],"moves_used":3,"moves_left":2,"max_moves":5,"sees_opponent":true,"opponent_pos":[1,1],"opponent_hint":"exact","last_msg":"Caught you.","inbox":[{"from":"COP","turn":1,"ts":"2026-06-27T00:00:01+00:00","text":"I am closing the west edge."},{"from":"COP","turn":3,"ts":"2026-06-27T00:00:03+00:00","text":"Caught you."}]}},"ground_truth":{"cop_pos":[1,1],"thief_pos":[1,1],"barriers":[],"moves_used":3},"score":{"cop":20,"thief":5}}
  ```
  **Check:** `uv run python -c "import json, pathlib; p=pathlib.Path('tests/test_gui/fixtures/replay_3x3.jsonl'); print(sum(1 for _ in p.open())); [json.loads(l) for l in p.open()]"` prints `3`.

- [ ] **C2** - `tests/test_gui/fixtures/replay_5x5.jsonl` - create - add one compact record with `obs.COP.grid` and `obs.THIEF.grid` set to `[5,5]`, Cop at `[0,0]`, Thief at `[4,4]`, and no `score` field. This proves old/missing-score logs degrade gracefully.
  **Check:** `uv run python -c "from src.gui.replay import load_run; r=load_run('tests/test_gui/fixtures/replay_5x5.jsonl'); print(r['grid'], r['final_score']['available'])"` prints `[5, 5] False`.

- [ ] **C3** - `tests/test_gui/fixtures/broken.jsonl` - create - add one invalid line `{not-json}` for error-path tests. Do not list it from the app's configured fixture run dir in normal tests unless the test expects unreadable metadata.
  **Check:** `uv run python -c "from pathlib import Path; print(Path('tests/test_gui/fixtures/broken.jsonl').read_text().strip())"` prints `{not-json}`.

---

## Phase D - replay unit tests

- [ ] **D1** - `tests/test_gui/test_replay.py` - create - add imports and fixture path constants:
  ```python
  from pathlib import Path

  import pytest

  from src.gui.replay import fog_view, ghost_marker, list_runs, load_run, running_score, to_frames

  FIXTURES = Path(__file__).with_name("fixtures")
  ```
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py` runs and reports collected tests after later boxes.

- [ ] **D2** - `tests/test_gui/test_replay.py` - edit - add `test_load_run_returns_frames_and_metadata` asserting the 3x3 run name, grid `[3, 3]`, three frames, first side `COP`, and final score `{"cop": 20, "thief": 5, "available": True}`.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_load_run_returns_frames_and_metadata` passes.

- [ ] **D3** - `tests/test_gui/test_replay.py` - edit - add `test_to_frames_is_resizable_for_3x3_and_5x5` asserting `replay_3x3` first frame board grid is `[3, 3]`, positions are `[0, 1]` and `[2, 2]`, and `replay_5x5` grid is `[5, 5]`.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_to_frames_is_resizable_for_3x3_and_5x5` passes.

- [ ] **D4** - `tests/test_gui/test_replay.py` - edit - add `test_conversation_accumulates_public_messages_only` asserting frame conversations are lengths 1, 2, 3; texts match the three fixture `message.text` values; and `"SECRET_REASONING_DO_NOT_SHOW"` is absent from `str(frame["conversation"])` for every frame.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_conversation_accumulates_public_messages_only` passes.

- [ ] **D5** - `tests/test_gui/test_replay.py` - edit - add `test_ghost_marker_uses_action_belief_and_error` using the first 3x3 record and asserting `ghost_marker(record) == {"guess": [2, 2], "error": 0}`.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_ghost_marker_uses_action_belief_and_error` passes.

- [ ] **D6** - `tests/test_gui/test_replay.py` - edit - add `test_fog_view_preserves_blind_noisy_full_without_leakage`. Assert the first `THIEF` fog has `mode == "blind"` and `opponent_pos is None`; the first `COP` fog has `mode == "noisy"`, `sees_opponent is False`, and hint `"southeast"`; the final `COP` fog has `mode == "full"` and exact `opponent_pos == [1, 1]`.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_fog_view_preserves_blind_noisy_full_without_leakage` passes.

- [ ] **D7** - `tests/test_gui/test_replay.py` - edit - add `test_telemetry_moves_left_and_running_score` asserting `moves_left` decreases in the 3x3 frames, `llm.latency_ms` is present, `telemetry_summary.llm_calls == 3`, and `running_score(frames)["cop"] == 20`.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_telemetry_moves_left_and_running_score` passes.

- [ ] **D8** - `tests/test_gui/test_replay.py` - edit - add `test_missing_optional_fields_degrade_gracefully` with `to_frames([{"turn": 1, "side": "COP"}])`; assert it returns one frame, score `available is False`, and empty fog dicts.
  **Check:** `uv run pytest -q tests/test_gui/test_replay.py::test_missing_optional_fields_degrade_gracefully` passes.

---

## Phase E - FastAPI app

- [ ] **E1** - `src/gui/app.py` - create - add imports and path helpers:
  ```python
  from __future__ import annotations

  from pathlib import Path

  import uvicorn
  from fastapi import FastAPI, HTTPException
  from fastapi.responses import FileResponse
  from fastapi.staticfiles import StaticFiles

  from src.game.config import load_config
  from src.gui.replay import list_runs, load_run


  def _static_dir() -> Path:
      return Path(__file__).with_name("static")


  def _safe_run_path(run_dir: Path, name: str) -> Path | None:
      if Path(name).name != name or not name.endswith(".jsonl"):
          return None
      root = run_dir.resolve()
      candidate = (root / name).resolve()
      if candidate.parent != root:
          return None
      return candidate
  ```
  **Check:** `uv run python -m py_compile src/gui/app.py` succeeds after later route functions exist.

- [ ] **E2** - `src/gui/app.py` - edit - add `create_app(config) -> FastAPI` using the verified FastAPI/StaticFiles shape:
  ```python
  def create_app(config) -> FastAPI:
      app = FastAPI(title="HW6 Cop-and-Thief Replay GUI")
      run_dir = Path(config.gui["run_dir"])
      static_dir = _static_dir()
      app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

      @app.get("/")
      def index():
          return FileResponse(static_dir / "index.html")

      @app.get("/api/runs")
      def api_runs():
          return {"runs": list_runs(run_dir)}

      @app.get("/api/runs/{name}")
      def api_run(name: str):
          path = _safe_run_path(run_dir, name)
          if path is None or not path.exists():
              raise HTTPException(status_code=404, detail="run not found")
          try:
              return load_run(path)
          except ValueError as exc:
              raise HTTPException(status_code=400, detail=str(exc)) from exc

      return app
  ```
  **Check:** `uv run python -c "from types import SimpleNamespace; from src.gui.app import create_app; print(create_app(SimpleNamespace(gui={'run_dir':'tests/test_gui/fixtures'})).title)"` prints the app title.

- [ ] **E3** - `src/gui/app.py` - edit - add CLI startup:
  ```python
  def main() -> None:
      config = load_config("config.yaml")
      uvicorn.run(create_app(config), host=config.gui["host"], port=config.gui["port"])


  if __name__ == "__main__":
      main()
  ```
  Do not hard-code the host or port in `src/gui/`.
  **Check:** `uv run python -c "from src.gui.app import main, create_app; print(callable(main), callable(create_app))"` prints `True True`.

- [ ] **E4** - `src/gui/__main__.py` - verify - now that `app.py` exists, compile the package entrypoint.
  **Check:** `uv run python -m py_compile src/gui/__main__.py src/gui/app.py` succeeds.

- [ ] **E5** - `src/gui/app.py` - audit - keep the file at or below 150 lines and keep it routes-only. If optional live mode is implemented later, put stream helpers in `src/gui/live.py`.
  **Check:** `uv run python -c "from pathlib import Path; p=Path('src/gui/app.py'); assert len(p.read_text().splitlines()) <= 150; print('ok')"`

- [ ] **E6** - `src/gui/app.py` - verify source guard - confirm only `app.py` imports FastAPI/Uvicorn; `replay.py` remains framework-free.
  **Check:** `uv run python -c "from pathlib import Path; replay=Path('src/gui/replay.py').read_text().lower(); app=Path('src/gui/app.py').read_text().lower(); assert 'fastapi' not in replay; assert 'uvicorn' in app; print('ok')"`

- [ ] **E7** - `src/gui/app.py` - path safety smoke - manually verify `_safe_run_path` rejects traversal and non-jsonl names.
  **Check:** `uv run python -c "from pathlib import Path; from src.gui.app import _safe_run_path as s; r=Path('tests/test_gui/fixtures'); print(s(r,'replay_3x3.jsonl') is not None, s(r,'../config.yaml'), s(r,'x.txt'))"` prints `True None None`.

---

## Phase F - static frontend

- [ ] **F1** - `src/gui/static/index.html` - create - add a compact app shell: linked stylesheet/script, run `<select>`, icon/text controls for previous/play/next, range scrubber, speed slider, fog-side segmented control, `<canvas id="board">`, conversation list, and telemetry/status panel. Keep it at or below 150 lines.
  **Check:** `uv run python -c "from pathlib import Path; p=Path('src/gui/static/index.html'); text=p.read_text(); assert '<canvas' in text and '/static/app.js' in text and '/static/style.css' in text; assert len(text.splitlines()) <= 150; print('ok')"`

- [ ] **F2** - `src/gui/static/app.js` - create - add state and fetch/load functions only:
  - `const state = { runs: [], run: null, frames: [], index: 0, timer: null, fogSide: "COP", speed: 700 };`
  - `async function fetchRuns()`
  - `async function loadRun(name)`
  - `function currentFrame()`
  - `function render()`
  `fetchRuns` must call `/api/runs`; `loadRun` must call `/api/runs/${encodeURIComponent(name)}`. Do not compute frame fields here.
  **Check:** `uv run python -c "from pathlib import Path; text=Path('src/gui/static/app.js').read_text(); missing=[n for n in ['/api/runs','function render','function currentFrame'] if n not in text]; assert not missing, missing; print('ok')"`

- [ ] **F3** - `src/gui/static/app.js` - edit - add `drawBoard(frame)`. It must read `frame.board.grid`, `cop_pos`, `thief_pos`, `barriers`, and `beliefs`; compute cell size from canvas dimensions and grid rows/cols; draw barriers, Cop, Thief, and translucent belief ghosts. It may compute pixels, but no game logic.
  **Check:** `uv run python -c "from pathlib import Path; text=Path('src/gui/static/app.js').read_text(); assert 'drawBoard' in text and 'frame.board.grid' in text and 'beliefs' in text; assert '5x5' not in text and '[5, 5]' not in text; print('ok')"`

- [ ] **F4** - `src/gui/static/app.js` - edit - add panel renderers:
  - `renderConversation(frame)` uses `frame.conversation` and `item.text`.
  - `renderTelemetry(frame)` uses `frame.score`, `frame.moves_left`, `frame.confidence`, `frame.intent`, and `frame.llm`.
  - `renderFog(frame)` uses `frame.fog[state.fogSide]` and never reads raw ground truth beyond `frame.board` already provided.
  The string `reasoning` must not appear in `app.js`.
  **Check:** `uv run python -c "from pathlib import Path; text=Path('src/gui/static/app.js').read_text(); missing=[n for n in ['renderConversation','renderTelemetry','renderFog'] if n not in text]; assert not missing, missing; assert 'reasoning' not in text; print('ok')"`

- [ ] **F5** - `src/gui/static/app.js` - edit - wire controls:
  - previous/next buttons update `state.index` within bounds;
  - play/pause uses `setInterval` and `clearInterval`;
  - scrubber updates `state.index`;
  - speed slider updates `state.speed`;
  - fog-side buttons set `state.fogSide` to `COP` or `THIEF`;
  - on page load, call `fetchRuns()`.
  **Check:** `uv run python -c "from pathlib import Path; text=Path('src/gui/static/app.js').read_text(); missing=[n for n in ['setInterval','clearInterval','addEventListener','fetchRuns()'] if n not in text]; assert not missing, missing; assert len(text.splitlines()) <= 150; print('ok')"`

- [ ] **F6** - `src/gui/static/style.css` - create - style a dense tool UI: two-column desktop layout, single-column mobile layout, stable canvas aspect, compact panels, no overlapping text, 8px or smaller border radius. Avoid a one-note purple/slate/beige/brown palette.
  **Check:** `uv run python -c "from pathlib import Path; text=Path('src/gui/static/style.css').read_text(); assert 'canvas' in text and '@media' in text; assert len(text.splitlines()) <= 150; print('ok')"`

---

## Phase G - FastAPI endpoint tests

- [ ] **G1** - `tests/test_gui/test_app.py` - create - add imports and a helper config:
  ```python
  from types import SimpleNamespace

  from fastapi.testclient import TestClient

  from src.gui.app import create_app


  def _client(run_dir="tests/test_gui/fixtures"):
      config = SimpleNamespace(gui={"run_dir": run_dir, "host": "127.0.0.1", "port": 8000})
      return TestClient(create_app(config))
  ```
  **Check:** `uv run pytest -q tests/test_gui/test_app.py` runs after tests are added.

- [ ] **G2** - `tests/test_gui/test_app.py` - edit - add `test_index_and_static_mount`. Assert `client.get("/")` returns `200`, content type includes HTML or octet-stream from `FileResponse`, and `client.get("/static/app.js")` returns `200`.
  **Check:** `uv run pytest -q tests/test_gui/test_app.py::test_index_and_static_mount` passes.

- [ ] **G3** - `tests/test_gui/test_app.py` - edit - add `test_api_runs_lists_fixture_runs`. Assert `/api/runs` returns `200`, JSON has key `runs`, and includes `replay_3x3.jsonl` with `turns == 3` and `grid == [3, 3]`.
  **Check:** `uv run pytest -q tests/test_gui/test_app.py::test_api_runs_lists_fixture_runs` passes.

- [ ] **G4** - `tests/test_gui/test_app.py` - edit - add `test_api_run_returns_run_json`. Assert `/api/runs/replay_3x3.jsonl` returns a `Run` with `name`, `grid`, `frames`, and `telemetry_summary`; assert the first frame has `conversation[0]["text"]`.
  **Check:** `uv run pytest -q tests/test_gui/test_app.py::test_api_run_returns_run_json` passes.

- [ ] **G5** - `tests/test_gui/test_app.py` - edit - add `test_api_run_rejects_missing_and_traversal`. Assert `/api/runs/missing.jsonl`, `/api/runs/..%2Fconfig.yaml`, and `/api/runs/not-json.txt` return `404`.
  **Check:** `uv run pytest -q tests/test_gui/test_app.py::test_api_run_rejects_missing_and_traversal` passes.

- [ ] **G6** - `tests/test_gui/test_app.py` - edit - add `test_main_uses_configured_host_port` by monkeypatching `src.gui.app.load_config` to return `SimpleNamespace(gui={...})` and monkeypatching `src.gui.app.uvicorn.run` to capture `host` and `port`. Assert captured values match the fake config.
  **Check:** `uv run pytest -q tests/test_gui/test_app.py::test_main_uses_configured_host_port` passes.

---

## Phase H - static guards, full verification, visual artifact

- [ ] **H1** - `tests/test_gui/test_static_guards.py` - create - add `test_gui_files_are_at_most_150_lines`, scanning every file under `src/gui/` and failing with filename and line count when over 150.
  **Check:** `uv run pytest -q tests/test_gui/test_static_guards.py::test_gui_files_are_at_most_150_lines` passes.

- [ ] **H2** - `tests/test_gui/test_static_guards.py` - edit - add `test_replay_has_no_forbidden_tier_imports`, asserting `src/gui/replay.py` does not contain `src.game`, `src.mcp_servers`, `src.orchestrator`, `src.strategy`, `src.agents`, `fastapi`, or `uvicorn`.
  **Check:** `uv run pytest -q tests/test_gui/test_static_guards.py::test_replay_has_no_forbidden_tier_imports` passes.

- [ ] **H3** - `tests/test_gui/test_static_guards.py` - edit - add `test_gui_has_no_hardcoded_grid_port_model_or_key`. Scan files under `src/gui/` for forbidden strings: `5x5`, `[5, 5]`, `"claude-`, `ANTHROPIC_API_KEY`, `api_key`, and `8000` outside comments/docs. Allow canvas pixel/CSS numeric values that are not game parameters.
  **Check:** `uv run pytest -q tests/test_gui/test_static_guards.py::test_gui_has_no_hardcoded_grid_port_model_or_key` passes.

- [ ] **H4** - `tests/test_gui/test_static_guards.py` - edit - add `test_frontend_never_mentions_reasoning`, asserting `reasoning` does not appear in `src/gui/static/app.js` or `index.html`.
  **Check:** `uv run pytest -q tests/test_gui/test_static_guards.py::test_frontend_never_mentions_reasoning` passes.

- [ ] **H5** - run targeted GUI tests - execute replay, app, and static guard tests together.
  **Check:** `uv run pytest -q tests/test_gui` passes.

- [ ] **H6** - run style and coverage gate - execute ruff and coverage on the new GUI Python. Use source coverage for `src.gui`; JS is intentionally thin and not part of pytest coverage.
  **Check:** `uv run ruff check src/gui tests/test_gui` and `uv run pytest -q tests/test_gui --cov=src.gui --cov-fail-under=85` both pass.

- [ ] **H7** - run compatibility suite - confirm Step 6 did not break prior work.
  **Check:** `uv run pytest -q` passes, including the existing 130 tests plus new GUI tests.

- [ ] **H8** - manual server smoke - run `uv run python -m src.gui`, open the configured URL from `config.gui`, load `replay_3x3.jsonl`, and verify board, conversation, ghosts, fog toggle, telemetry/status, and controls work. Stop the server before ending the session.
  **Check:** record the opened URL and observed fixture name in Developer notes.

- [ ] **H9** - `docs/step6_gui/gui_replay_screenshot.png` - create - capture one screenshot showing board + conversation + belief ghosts for README visual proof. Keep the image under `docs/step6_gui/`.
  **Check:** `uv run python -c "from pathlib import Path; p=Path('docs/step6_gui/gui_replay_screenshot.png'); print(p.exists(), p.stat().st_size if p.exists() else 0)"` prints `True` and a non-zero size.

---

## Phase I - OPTIONAL stretch: live/SSE endpoint (cuttable)

These boxes are optional. Skipping all of Phase I does not block Step 6 done.

- [ ] **I1 OPTIONAL** - `src/gui/live.py` - create - add a tiny SSE helper using the verified FastAPI `StreamingResponse` shape. It should expose `def unavailable_stream(reason: str)` yielding one `event: unavailable` message and no game-driving imports unless live mode is deliberately attempted.
  **Check:** `uv run python -m py_compile src/gui/live.py` succeeds.

- [ ] **I2 OPTIONAL** - `src/gui/app.py` - edit - add `GET /api/live` route that imports `StreamingResponse`, returns `StreamingResponse(unavailable_stream("live mode not configured"), media_type="text/event-stream")`, and does not affect replay endpoints.
  **Check:** `uv run pytest -q tests/test_gui/test_app.py` still passes.

- [ ] **I3 OPTIONAL** - `tests/test_gui/test_live_optional.py` - create - add a `TestClient` test asserting `/api/live` returns `200` and content type starts with `text/event-stream`, or returns a documented unavailable state if the route is intentionally disabled.
  **Check:** `uv run pytest -q tests/test_gui/test_live_optional.py` passes.

---

## Acceptance coverage matrix

| PRD acceptance | TODO boxes | Tests / checks |
|----------------|------------|----------------|
| AC1 FastAPI starts and `/` shows replay UI | A1-A5, E1-E7, F1-F6, H8 | `python -m src.gui`, `test_index_and_static_mount`, manual smoke |
| AC2 3x3 and 5x5 resizability | B2-B6, C1-C2, D3 | `test_to_frames_is_resizable_for_3x3_and_5x5` |
| AC3 Conversation and `reasoning` privacy | B3, B5, C1, D4, H4 | `test_conversation_accumulates_public_messages_only`, frontend guard |
| AC4 Belief ghosts | B3, B5, C1, D5, F3 | `test_ghost_marker_uses_action_belief_and_error` |
| AC5 Per-agent fog modes | B3, B5, C1, D6, F4 | `test_fog_view_preserves_blind_noisy_full_without_leakage` |
| AC6 Telemetry and score/status | B4-B6, C1-C2, D7, F4 | `test_telemetry_moves_left_and_running_score`; missing-score fixture |
| AC7 Endpoints via TestClient | E1-E7, G1-G6 | `tests/test_gui/test_app.py` |
| AC8 Gate-clean / no hard-code | A1, H1-H6 | line-count, forbidden import, hard-code, ruff, coverage checks |
| AC9 Backward compatibility | FR replay isolation, H2, H7 | forbidden-tier guard plus full `uv run pytest -q` |
| AC10 README screenshot | H8-H9 | manual smoke plus screenshot file check |
| AC11 Optional live/SSE | I1-I3 | optional `test_live_optional.py`; can be cut |

## Definition of Done
- [ ] Required boxes A1-H9 are ticked and their Checks passed.
- [ ] Optional Phase I is either fully passing or explicitly skipped as stretch.
- [ ] All PRD acceptance criteria 1-10 hold (`PRD_step6_gui.md` Section 7); criterion 11 is optional.
- [ ] No hard-coded grid size, GUI port, model string, API key, or hidden reasoning surface exists in `src/gui/`.
- [ ] Every file under `src/gui/` is at most 150 lines.
- [ ] `uv run ruff check src/gui tests/test_gui` passes.
- [ ] `uv run pytest -q tests/test_gui --cov=src.gui --cov-fail-under=85` passes.
- [ ] `uv run pytest -q` passes, including the existing 130 tests.
- [ ] `docs/_system/ROADMAP.md` is updated by the Developer after implementation: set Step 6 to done and append a progress-log line.
