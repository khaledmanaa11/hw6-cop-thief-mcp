# PRD - Step 6: Graphical User Interface

- **Status:** triplet-built
- **Source:** `DECISION_step6_gui.md`; SDK ground truth: `SDK_REFERENCE_fastapi.md`
- **Assignment references:** Section 13 Table 4 (GUI recommended engineering step); Sections 2/3 (graded communication/orchestration, already surfaced by Step 5); Workflow Section 6 (no hard-coding, resizable board, server/client split, free natural language, Dec-POMDP).

## 1. Problem & context
Steps 1-5 can run the full Cop-and-Thief series locally and record one JSONL line per ply. The Step 5 record now contains the important graded evidence: free-text messages, per-agent observations, private beliefs, belief error, intent/confidence, and LLM telemetry. But the evidence is still hard to inspect: a grader or README reader must read terminal output or raw JSONL.

Step 6 adds a presentation-tier GUI over those existing logs. It does not change the game, agents, MCP servers, LLM prompts, or replay contract. It reads a recorded JSONL run, shapes it into render-ready frames in Python, and serves a small HTML/canvas viewer that can replay the board, conversation, beliefs, fog, telemetry, and score-like run status.

## 2. Goal & success metric
After this step, `python -m src.gui` starts a local FastAPI app on the configured GUI host/port. Opening `/` shows a web replay UI for committed JSONL fixtures and real `runs/*.jsonl` files. The UI makes the Step 5 natural-language and Dec-POMDP evidence visible while preserving privacy: `reasoning` remains logged but never appears in the conversation panel.

Success is measured by deterministic tests, not a browser automation suite: `replay.py` unit tests cover all data shaping, `app.py` endpoint tests use FastAPI `TestClient`, the existing 130 tests keep passing, every `src/gui/` file stays at or below 150 lines, and the new GUI code keeps pytest coverage at or above 85%.

## 3. Stories
- As the **record/replay layer**, I need to load a Step 5 JSONL run into cumulative frames so that replay is deterministic and key-free.
- As the **orchestrator contract owner**, I need the GUI to consume the existing per-ply JSONL shape read-only so that Step 6 cannot break engine, server, or agent behavior.
- As the **grader / README author**, I need board movement, free-text conversation, belief ghosts, fog, and telemetry visible together so that the orchestration/NL story is inspectable.
- As the **frontend renderer**, I need one self-contained frame per ply so that JavaScript only draws data and does not reimplement game logic.
- As the **privacy boundary**, I need `reasoning` excluded from all conversation payloads so that private LLM thoughts never become opponent-visible or GUI-visible dialogue.

## 4. Functional requirements
- **FR-GUI1 - Presentation-tier package.** Add `src/gui/` with replay shaping, FastAPI routes, and static frontend assets. The replay path must not import or modify `src/game`, `src/mcp_servers`, `src/orchestrator` runtime loops, `src/strategy`, or `src/agents`.
- **FR-GUI2 - JSONL replay loader.** `load_run(path: str) -> Run` reads a JSONL run and returns render-ready metadata and frames. Invalid JSON lines raise a clear `ValueError`; missing optional Step 5 fields degrade gracefully.
- **FR-GUI3 - Pure frame transform.** `to_frames(records: list[dict]) -> list[Frame]` is the central, unit-tested transform. It accumulates conversation, board state, belief markers, fog projections, telemetry, moves left, and score/status data into self-contained frames.
- **FR-GUI4 - Run picker API.** `list_runs(run_dir) -> list[RunMeta]` lists available `.jsonl` runs with name, mtime, turn count, and grid when readable.
- **FR-GUI5 - FastAPI app.** `create_app(config) -> FastAPI` serves `/`, `/static/*`, `GET /api/runs`, and `GET /api/runs/{name}`. API routes return JSON dicts/lists and are tested with `fastapi.testclient.TestClient`.
- **FR-GUI6 - Canvas replay controls.** The static frontend renders an R-by-C grid from each frame, draws Cop, Thief, barriers, belief ghosts, and supports previous/next/play/pause, scrubber, speed, and fog-side toggle.
- **FR-GUI7 - Conversation panel.** Frames expose only the public `message` envelope (`from`, `turn`, `ts`, `text`) and accumulate oldest-to-newest through the current ply. `action.reasoning` must never appear in any conversation item.
- **FR-GUI8 - Belief ghosts.** Frames expose `beliefs.COP` and `beliefs.THIEF` as `{guess, error}` using `action.belief` and `action.belief_error` from the record.
- **FR-GUI9 - Per-agent fog.** Frames expose `fog.COP` and `fog.THIEF` from `obs.COP` and `obs.THIEF` exactly as recorded, covering `blind`, `noisy`, and `full` observation modes without leaking extra truth.
- **FR-GUI10 - Telemetry and score/status panel.** Frames expose `moves_left`, `confidence`, `intent`, `llm`, and a running score/status object. If official point totals are absent from older JSONL records, the GUI must show an explicit unavailable/zero status rather than crashing.
- **FR-GUI11 - Config-driven startup.** Add a trailing-optional `gui:` config block with `host`, `port`, and `run_dir` (defaulting to `output.run_dir` when omitted). No GUI host, port, run directory, model string, API key, or grid size is hard-coded in `src/gui/`.
- **FR-GUI12 - Optional live stretch only.** A live SSE endpoint may be added behind an optional TODO box using `StreamingResponse`. It is not required for Step 6 done.

## 5. Non-functional requirements
- **NFR1 - config-driven:** GUI host, port, and run directory come from `config.yaml` / `Config.gui`; `run_dir` falls back to `output.run_dir`.
- **NFR2 - resizable:** every board dimension comes from each record's `obs.*.grid` or fixture/record metadata. The GUI must never assume 5x5 and must pass a committed 3x3 fixture test.
- **NFR3 - thin JS / Python coverage:** all data shaping lives in `src/gui/replay.py` and route wiring in `src/gui/app.py`; JavaScript is a minimal renderer of backend frames.
- **NFR4 - privacy:** `reasoning` may remain in raw JSONL but must not be copied into `Frame.conversation` or rendered by the frontend.
- **NFR5 - file size:** every file under `src/gui/` is at most 150 lines. Split only if needed; keep responsibilities narrow.
- **NFR6 - uv-only dependencies:** add FastAPI dependencies with `uv add`, using the pins in `SDK_REFERENCE_fastapi.md`.
- **NFR7 - quality gate:** ruff clean, GUI Python coverage at or above 85%, and the existing 130 tests continue to pass.
- **NFR8 - no secrets/network in tests:** GUI tests use committed fixtures and `TestClient`; no browser, real socket, API key, LLM call, or external network is required.

## 6. In scope / Out of scope
**In scope:** `src/gui/` replay module, FastAPI app, static HTML/canvas/CSS frontend, `gui:` config block, committed 3x3 and 5x5 JSONL fixtures, replay unit tests, endpoint tests, static guard tests, and a README-ready screenshot artifact.

**Out of scope:** changing the Step 5 JSONL writer, changing engine rules, changing MCP tools, changing agents/prompts, cloud deployment/public URL (Step 7), Gmail JSON report (Step 8), and live game driving except for the optional SSE stretch.

## 7. Acceptance criteria
1. `python -m src.gui` starts FastAPI on `config.gui.host` / `config.gui.port`; opening `/` shows a board that replays a committed JSONL run with previous/next/play controls. Verified by manual smoke plus `TestClient` route tests.
2. Board resizability is proven: a 3x3 fixture yields grid `[3, 3]` and correct token positions, and a 5x5 fixture yields `[5, 5]`. Verified by `to_frames` tests.
3. The conversation panel data shows actual `message.text` values, oldest-to-newest, through the current ply. A test asserts fixture envelopes match and `reasoning` is absent from every conversation item.
4. Belief ghost data is correct: `ghost_marker(record)` returns the current side's `action.belief` and `action.belief_error`. Verified by fixture tests.
5. Fog data is correct: `fog_view(record, side)` returns the recorded observation projection. Tests cover `blind` hiding the opponent, `noisy` showing hint/region only when not exact, and `full` showing the exact cell.
6. Telemetry and score/status data are exposed: frames include `moves_left`, `confidence`, `intent`, `llm`, and running score/status. Tests cover roll-up on a multi-turn fixture and graceful handling when official score fields are absent.
7. Endpoints work without sockets or keys: `GET /api/runs` lists committed fixtures and `GET /api/runs/{name}` returns a valid `Run` JSON object through FastAPI `TestClient`.
8. Gate-clean: every `src/gui/` file is at most 150 lines; static guards find no literal grid-size assumption, no hard-coded GUI port, no model string, and no API key in `src/gui/`; dependencies were added with `uv`; ruff and coverage pass.
9. Backward compatibility holds: the existing 130 tests still pass, and the replay path does not modify `src/game`, `src/mcp_servers`, `src/orchestrator`, `src/strategy`, or `src/agents`.
10. A README-ready visual artifact exists: at least one screenshot of the board plus conversation plus belief ghosts is produced under `docs/step6_gui/`.
11. Optional only: a live SSE endpoint can stream frames and degrade gracefully when live dependencies are unavailable. This criterion is not required for Step 6 done.

## 8. Dependencies
- **Upstream (needs):** Step 3/5 JSONL contract from `src/orchestrator/referee.py`; observation shapes, `ReplayLog`, and `Telemetry` from `src/orchestrator/recorders.py`; config loader from `src/game/config.py`; existing `output.run_dir` in `config.yaml`; verified FastAPI/Uvicorn/TestClient shape from `SDK_REFERENCE_fastapi.md`.
- **Downstream (unblocks):** Step 7 can deploy the same FastAPI app; Step 8 can reuse `load_run` / `to_frames` style parsing for report tooling; README can use the screenshot as visual proof of correct communication.

## 9. References
- `docs/step6_gui/DECISION_step6_gui.md`
- `docs/step6_gui/SDK_REFERENCE_fastapi.md`
- `docs/_system/WORKFLOW.md`
- `src/orchestrator/referee.py` per-ply record keys: `turn`, `side`, `move`, `verdict`, `message`, `action`, `obs`, `ground_truth`
- `src/orchestrator/recorders.py` observation modes: `blind`, `noisy`, `full`; replay and telemetry helpers
- `src/game/config.py` trailing-optional config pattern
- `config.yaml` keys: `output.run_dir`, new `gui.host`, `gui.port`, `gui.run_dir`
