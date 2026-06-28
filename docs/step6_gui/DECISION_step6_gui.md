# DECISION — Step 6: Graphical User Interface

- **Roadmap position:** step 6 of 8 (`step6_gui`)
- **Date discussed:** 2026-06-27
- **Status:** decision-written
- **Assignment references:** §13 Table 4 (GUI is a recommended engineering step, **not** the graded core — §2/§3 grade orchestration/NL, already delivered in Step 5); the cross-cutting README deliverable "visual proof of correct communication"; the standing **no-hard-coding / resizable-board** constraint (WORKFLOW §6). The GUI consumes — and must not modify — the Step-3/5 JSONL replay contract and the engine/server/agent tiers.

## 1. What this step is (one paragraph)
Step 6 gives the project a **watchable front-end**. Until now a run is provable only through the terminal ASCII board and the `runs/<ts>.jsonl` replay log. Step 6 adds a **web GUI** (FastAPI backend + an HTML/`<canvas>` frontend) that **replays a recorded JSONL series**: it draws the grid, the Cop, the Thief, and barriers turn-by-turn with a scrubber, and — crucially for this assignment — it renders the four things that make the graded core visible: the **free-text conversation** each side sends, each agent's **belief ghost** (where it *thinks* the opponent is vs. the truth, with Chebyshev error), each agent's **partial-observation fog** (the Dec-POMDP ⟨Ωᵢ⟩ made visual), and a **telemetry/score** panel. It is a presentation layer over data that already exists — **no new game logic, no LLM calls, no engine/server/agent changes**. A "live" mode that drives a real game is an explicitly-optional stretch goal; the primary, gradeable artifact is the deterministic replayer.

## 2. What it adds to the project
- A new **presentation-tier package** `src/gui/`:
  - `replay.py` — **all data-shaping logic, fully unit-tested**: load a JSONL file → an ordered list of render-ready **frames**; compute belief-ghost coordinates, per-agent fog projection, running score, and conversation history. The frontend stays dumb.
  - `app.py` — a thin **FastAPI** app: list available runs, serve one run's frames as JSON, serve the static page. (Optional `live` SSE endpoint behind a stretch box.)
  - `static/` — `index.html`, `app.js`, `style.css`: a `<canvas>` board + side panels that render exactly what the backend hands them.
- A **run-list / run-load HTTP API** decoupling the visualizer from the orchestrator (the GUI reads files, it does not import the game loop for replay).
- A **README visual-proof artifact**: screenshots / a short GIF of a series replaying — satisfies the cross-cutting "visual proof of correct communication" deliverable.
- A new test package `tests/test_gui/` exercising `replay.py` and the FastAPI endpoints (via `TestClient`) against a small committed JSONL fixture — **no browser, no network, no API key**.

## 3. Scope
**In scope:**
- **Replay-first web GUI**: open a `runs/<ts>.jsonl`, scrub/step/auto-play through turns; board rendered from the record's `grid` field (resizable, never hard-coded 5×5).
- **Four panels** (all chosen by the Director):
  1. **Conversation log** — the per-turn `message` envelopes from both sides (the visible artifact of the graded NL core), oldest→newest, highlighting the current turn.
  2. **Belief ghosts overlay** — draw `action.belief` as a translucent marker beside the true opponent cell, labelled with `belief_error` (Chebyshev). Visualizes deception working or failing.
  3. **Per-agent fog / partial view** — a toggle to show what each agent actually sees (`obs.{COP,THIEF}`): `blind` = opponent hidden, `noisy` = hint/region only, `full` = exact. The Dec-POMDP ⟨Ωᵢ⟩ made visual.
  4. **Telemetry + score panel** — running score, `moves_left`, and per-ply `confidence`/`intent` + LLM `latency_ms`/tokens/cost from the record.
- **Thin-JS / logic-in-Python architecture** so the Segal gate (pytest coverage ≥85%) is met by testing `replay.py` + `app.py`; JS stays a minimal renderer.
- **Config-driven**: a trailing-optional `gui:` block (host/port/default run dir). No literal grid sizes, ports, or model strings in `src/gui/`.
- Resizability proven by a **3×3 fixture** replaying correctly.

**Out of scope (deferred):**
- A **live** game-driving mode (start a real series, stream plies). Kept as an explicit **stretch box** in the TODO (graceful: disabled if no servers/API key). The graded deliverable is the replayer.
- Cloud hosting / public URL of the GUI → **Step 7** (the same FastAPI app can later be deployed; replay stays local).
- The JSON-only Gmail report → **Step 8** (reads the same JSONL).
- Any change to game rules, scoring, the MCP server tool contract, the agents, or the JSONL record shape — **unchanged**. Step 6 is a strict consumer of the Step-5 contract.

## 4. Chosen approach (and what we rejected)
**Decision:** A **FastAPI + HTML/`<canvas>` web GUI** that **replays a recorded JSONL file**, with all data-shaping in a unit-tested Python module (`replay.py`) and a thin JS renderer. Four panels: conversation, belief ghosts, per-agent fog, telemetry/score. Live-drive is an optional stretch goal.

**Why:** Step 6 is presentation, not the graded core, so the priority is **clear visual proof at low risk**. Replaying the JSONL that Step 5 already emits means the GUI needs **zero new game logic and never touches the API**, so it's deterministic, demoable with no key, and decoupled from the nondeterministic LLM — consistent with Step 5's "reproducibility by recording" decision. The web stack screenshots/GIFs cleanly for the README and **foreshadows Step 7** (the FastAPI app can later be cloud-hosted). Putting all logic in Python keeps the strict pytest-coverage gate satisfiable while the JS stays a dumb canvas. The belief-ghost + fog + conversation panels are deliberately the ones that **re-surface the §2/§3 deception/Dec-POMDP story visually** — Step 6 reinforces the grade earned in Step 5 rather than adding ungraded mechanics.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Web: FastAPI + HTML/canvas | ✅ chosen (Director) | Best polish, screenshots/GIF for README, foreshadows Step-7 cloud deploy |
| Python desktop (Tkinter/pygame) | ❌ rejected | Less shareable, reuses nothing for Step 7, weaker artifact |
| Terminal TUI (rich/textual) | ❌ rejected | Trivial but weakest "GUI" claim; ASCII board already exists |
| Replay-first, live optional | ✅ chosen (Director) | Deterministic, no-key demo; matches Step-5 record-and-replay; live = stretch |
| Live-only (real-time during run) | ❌ rejected | Needs servers + API key to demo, nondeterministic, fragile for grading |
| Replay-only (no live at all) | ❌ rejected | Slightly under-sells; keep live as a cheap optional stretch box |
| All four panels (chat, ghosts, fog, telemetry) | ✅ chosen (Director) | The belief/fog/chat visuals are exactly where Step 6 reinforces §2/§3 |
| Logic in JS, fat frontend | ❌ rejected | JS isn't covered by pytest → breaks the Segal ≥85% coverage gate |
| Logic in Python (`replay.py`), thin JS | ✅ chosen | Coverage stays green; JS is a minimal renderer of backend frames |

## 5. Dependencies & interfaces
- **Consumes from prior steps (read-only):**
  - The **JSONL ply record** written by `src/orchestrator/referee.py` via `recorders.ReplayLog`. Per-ply shape (Step-5, do not change): `turn`, `side`, `move`, `verdict`, `message` (`{from,turn,ts,text}`), `action` (`{message, belief, belief_error, confidence, intent, reasoning, llm}`), `obs.{COP,THIEF}` (mode-driven partial views incl. `opponent_hint`/`sees_opponent`), and `ground_truth` (`{cop_pos, thief_pos, barriers, moves_used}`).
  - `output.run_dir` (default `runs`) for where logs live; `observation.mode` for labelling the fog panel.
  - Conceptually mirrors `recorders.render_board` (the ASCII renderer) — the canvas is its visual twin, driven by `ground_truth`.
- **Exposes to later steps:**
  - A **FastAPI app object** and `static/` bundle that **Step 7** can deploy to the cloud unchanged (only host/binding differs).
  - A `load_run(path) -> list[Frame]` / `list_runs(run_dir)` helper reusable by any later viewer/report tooling.
- **Touches config keys:** adds top-level **`gui:`** (trailing-optional, mirroring `output`/`strategy`/`agents`/`observation`): `host`, `port`, `run_dir` (defaults to `output.run_dir`). **No change** to any existing key. No secrets.

## 6. Binding constraints (from the assignment)
- **Resizable / no hard-coding:** the board is drawn from each record's `grid` `[rows, cols]`; **no literal 5×5** anywhere in `src/gui/`. Host/port/run-dir from config. Prove on a **3×3 fixture**.
- **Presentation only — do not cross tiers:** `src/gui/` must not import or mutate the engine, MCP servers, or agents for the replay path (it reads files). The MCP server/client split is untouched.
- **No new secrets:** the GUI needs no API key for replay; if the optional live mode is built, the key still comes only from `ANTHROPIC_API_KEY` env (never in config/code/repo).
- **Dec-POMDP made visible:** the fog and belief-ghost panels render the existing `obs`/`belief` data — Step 6 visualizes the formal model, it does not redefine it.
- **Segal submission gate:** every file in `src/gui/` ≤150 lines (split `app.py`/`replay.py`/JS accordingly), `uv`-only deps, ruff-clean, and pytest coverage ≥85% — which is why all logic lives in the tested Python layer.

## 7. Key design decisions
- **Files/modules to create:**
  - `src/gui/__init__.py`
  - `src/gui/replay.py` — `load_run(path) -> Run`; `list_runs(run_dir) -> list[RunMeta]`; `to_frames(records) -> list[Frame]`; pure helpers `ghost_marker(record)`, `fog_view(record, side)`, `running_score(frames)`. **No FastAPI, no I/O beyond reading the file** → trivially unit-testable.
  - `src/gui/app.py` — `create_app(config) -> FastAPI`; routes `GET /` (page), `GET /api/runs` (list), `GET /api/runs/{name}` (frames JSON), `GET /static/*`. Thin: delegates all shaping to `replay.py`. `__main__` runs `uvicorn` on `gui.host`/`gui.port`.
  - `src/gui/static/index.html`, `app.js`, `style.css` — canvas board + four panels; `app.js` fetches `/api/runs/{name}`, holds a `currentTurn` index, and on each step redraws from the frame (play/pause, ◀/▶ step, speed slider, fog toggle per side).
  - `config.yaml` — append the `gui:` block.
  - `tests/test_gui/` — see acceptance; includes a small committed JSONL fixture (a 3×3 run and a 5×5 run).
- **Core data structures:**
  - `Frame` = `{turn, side, board:{grid:[r,c], cop_pos, thief_pos, barriers}, message, conversation:[…cumulative…], beliefs:{COP:{guess,error},THIEF:{…}}, fog:{COP:obs, THIEF:obs}, score:{cop,thief}, moves_left, llm, confidence, intent}` — one self-contained render unit per ply (the JS needs no cross-frame state).
  - `Run` = `{name, grid, frames:[Frame…], final_score, telemetry_summary}`.
  - `RunMeta` = `{name, mtime, turns, grid}` for the run picker.
- **Key signatures (intent):**
  - `load_run(path: str) -> Run` — parse JSONL lines, fold into cumulative frames (conversation accumulates oldest→newest; score updates on sub-game boundaries / final record).
  - `to_frames(records: list[dict]) -> list[Frame]` — the pure transform (the heart of the coverage).
  - `create_app(config) -> FastAPI` — wires routes to `list_runs`/`load_run`; `run_dir` from `config.gui.run_dir`.
- **Rendering intent (JS, kept minimal):** canvas draws an R×C grid from `frame.board.grid`; `C`/`T` tokens at `cop_pos`/`thief_pos`; `#` at barriers; a translucent ghost at `beliefs.<side>.guess`; the fog toggle dims cells the selected side cannot see per its `obs`. All positions come from the frame — JS computes nothing about the game.

## 8. Acceptance criteria (how we know the step is done)
1. `python -m src.gui` starts a FastAPI server on the configured host/port; opening `/` shows a board that **replays a committed JSONL run**, advancing Cop/Thief/barriers turn-by-turn via ◀/▶/play.
2. **Board is resizable:** loading the **3×3 fixture** renders a 3×3 grid (not 5×5); a test asserts `to_frames` yields the right grid and token positions for both a 3×3 and a 5×5 fixture.
3. **Conversation panel** shows the actual free-text `message.text` for each side per turn, accumulating oldest→newest; a test asserts the frame's `conversation` matches the fixture's envelopes (and that **`reasoning` is never surfaced** to the panel).
4. **Belief ghosts:** each frame carries `beliefs.{COP,THIEF}` with `guess` + `error`; a test asserts `ghost_marker` matches `action.belief` and `belief_error` from the record.
5. **Per-agent fog:** `fog_view(record, side)` returns the side's `obs` projection; a test asserts `blind` hides the opponent, `noisy` exposes only a hint/region, `full` exposes the exact cell — straight from the record, no leakage added.
6. **Telemetry/score:** the panel shows running score, `moves_left`, and per-ply `confidence`/`intent`/`llm`; a test asserts `running_score` is correct across a multi-turn fixture.
7. **Endpoints:** `GET /api/runs` lists committed fixtures and `GET /api/runs/{name}` returns valid `Run` JSON; tested via FastAPI `TestClient` — **no browser, no network, no API key**.
8. **Gate-clean:** every `src/gui/` file ≤150 lines; grep finds no literal grid number, no port, no model string, no API key in `src/gui/`; deps added via `uv`; ruff clean; coverage ≥85% on the new Python.
9. **Backward compatibility:** the existing 130 tests still pass; nothing in `src/game`, `src/mcp_servers`, `src/orchestrator`, `src/strategy`, `src/agents` is modified for the replay path.
10. **README artifact:** at least one screenshot (board + conversation + ghosts) is produced for the README's visual-proof deliverable.
11. *(Stretch, optional)* a `live` SSE endpoint can drive `run_series` and stream frames; degrades gracefully (clear "live unavailable" state) when servers/API key are absent. Not required for "done".

## 9. Resolved questions / open items
- **Q:** Rendering tech? → **A:** **Web — FastAPI backend + HTML/`<canvas>` frontend** (Director). Best polish + README artifact + Step-7 foreshadowing.
- **Q:** Replay, live, or both? → **A:** **Replay-first, live optional** (Director). Primary deliverable is the deterministic JSONL replayer; live-drive is an explicit stretch box.
- **Q:** Which panels? → **A:** **All four** — conversation, belief ghosts, per-agent fog, telemetry/score (Director). These are exactly the §2/§3 deception/Dec-POMDP visuals.
- **Q (Planner's call, Director may veto):** How to keep the pytest-coverage gate green with a JS frontend? → **A:** **Thin-JS / logic-in-Python** — all shaping in `replay.py` (unit-tested) + `app.py` (TestClient-tested); JS only draws backend frames.
- **Still open (note for Builder):** the **exact live FastAPI + uvicorn API** (`FastAPI`, route decorators, `StaticFiles` mount, `TestClient`, `uvicorn.run(host,port)`, and — if the live stretch is attempted — `StreamingResponse`/SSE) must be **verified against the live SDK via context7** before writing the TODO, the same "verify the live API first" discipline Steps 2–5 used. Pin `fastapi`+`uvicorn` versions in the triplet.

## 10. Notes for the Builder session
- **Put the most TODO detail in `replay.py`** — `to_frames` is the substance and the coverage. Spell out the fold from raw JSONL records to cumulative `Frame`s box-by-box (conversation accumulation, score roll-up at sub-game boundaries, ghost/fog/telemetry extraction) with copy-paste code. `app.py` and the JS are thin and mostly mechanical.
- **Commit a tiny JSONL fixture** (one short 3×3 run + one 5×5 run, a handful of plies each, hand-written or captured from a `FakeLLM` series) under `tests/test_gui/fixtures/` so every test is deterministic and key-free. Do **not** depend on a live `runs/` file.
- **Reuse the contract, don't re-derive it.** Read the real per-ply record shape from `referee.py` (§5 above) and `recorders.observe`'s mode outputs; the GUI must consume those fields verbatim. If a field is missing in older logs, degrade gracefully (e.g. no-belief frame), don't crash.
- **Resizability is a hard test, not a hope:** assert a 3×3 fixture renders 3×3. No `5`/`25`/port/model literals in `src/gui/` — pull host/port/run_dir from the `gui:` config block (trailing-optional, mirror `output`/`agents`).
- **Never surface `reasoning`.** It's logged-but-private; the conversation panel shows only `message.text`. Add a test that asserts `reasoning` never appears in any frame's conversation payload (mirrors the Step-5 two-channel discipline).
- **Keep files ≤150 lines** (Segal gate): split JS into `app.js` (control/fetch) and, if needed, a small `draw.js`; keep `app.py` routes-only and `replay.py` logic-only.
- **Verify FastAPI/uvicorn live** (context7) before writing the TODO; treat the `live` SSE endpoint as a clearly-marked optional stretch box that can be cut without affecting "done".
- **Config snippet to add (trailing-optional):**
  ```yaml
  gui:
    host: "127.0.0.1"
    port: 8000
    run_dir: "runs"      # defaults to output.run_dir; where JSONL logs are read from
  ```
