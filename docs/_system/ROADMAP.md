# ROADMAP — HW6 Dual AI Agent (Cop & Thief) via MCP

Single source of truth for **where we are**. Every new session reads this first.
Source: assignment §13, Table 4 (recommended engineering priority order).

## Status legend

| Mark | Meaning |
|------|---------|
| ⬜ | not started |
| 🗣️ | being discussed (Planner session in progress) |
| 📄 | DECISION written |
| 📦 | triplet (PRD/PLAN/TODO) built |
| 🔨 | implementing (Developer working through TODO) |
| ✅ | done (all TODO boxes pass + PRD acceptance met) |

## The 8 steps

| # | Slug / folder | Step | What it adds to the project | Status |
|---|---------------|------|------------------------------|--------|
| 1 | `step1_game_logic`     | Game logic & rules        | Pure engine: grid, movement, barriers, capture, scoring, sub-game/game loop, `config.yaml`. No MCP, no LLM. | ✅ |
| 2 | `step2_mcp_infra`      | Basic MCP infrastructure  | Two separate FastMCP servers (Cop, Thief) exposing tools (validate-location, send-message). Plumbing only. | ⬜ |
| 3 | `step3_local_run`      | Full local run            | Wire engine + both agents + both servers on localhost (separate ports); a full 6-sub-game series runs end-to-end locally. | ⬜ |
| 4 | `step4_decision_engine`| Decision mechanism        | The strategy "brain": heuristic / distance-based / Q-Table so agents pursue & evade. | ⬜ |
| 5 | `step5_nl_integration` | Natural-language integration | Replace structured messages with free-text LLM messages — agents talk, infer location, deceive. (Graded core.) | ⬜ |
| 6 | `step6_gui`            | Graphical user interface  | Visual board: real-time movement, barriers, logs. | ⬜ |
| 7 | `step7_cloud_deploy`   | Cloud distributed deployment | Push MCP servers to cloud with tokens/secure tunnels/cyber hygiene; publish 2 public URLs. | ⬜ |
| 8 | `step8_gmail_api`      | Gmail API reporting       | Auto-send the JSON-only report email to the lecturer after 6 sub-games. | ⬜ |

## Cross-cutting deliverables (not a "step", tracked separately)

- `README.md` with the **Dec-POMDP** formal model, architecture-challenge analysis,
  and visual/CLI proof of correct communication.
- `config.yaml` (single source of game parameters — no hard-coding).
- Sanity-check escalation across grids: 2×2 → 3×3 → 4×4 → 5×5.
- Optional **inter-group bonus** competition (worth up to 10 pts, separate JSON report).

## Fixed parameters (from the assignment — do not drift)

| Key | Default | Meaning |
|-----|---------|---------|
| `grid_size` | `[5, 5]` | board dimensions (must be resizable) |
| `max_moves` | `25` | max moves per sub-game |
| `num_games` | `6` | sub-games per series |
| `max_barriers` | `5` | barriers the Cop may place per sub-game |
| `scoring.cop_win` | `20` | Cop score when Cop captures |
| `scoring.thief_win` | `10` | Thief score when Thief survives |
| `scoring.cop_loss` | `5` | Cop score when Thief survives |
| `scoring.thief_loss` | `5` | Thief score when captured |

Report email target: `rmisegal+uoh26b@gmail.com` (JSON body only).

## Progress log

<!-- Append one line per session: date — step — what changed. Newest at bottom. -->
- 2026-06-25 — system — scaffolded `docs/_system/` (WORKFLOW, ROADMAP, 4 templates). No step content yet.
- 2026-06-25 — step1 — Planner session: read PDF §4, locked all rules, wrote `DECISION_step1_game_logic.md`. Step 1 → 📄. Next: Builder session (triplet).
- 2026-06-25 — step1 — Builder session: produced `PRD_step1_game_logic.md`, `PLAN_step1_game_logic.md`, and `TODO_step1_game_logic.md`. Step 1 → 📦.
- 2026-06-25 — step1 — Triplet review: patched TODO+PLAN — added boxes for `apply_move`, result dataclasses, `initial_state`/start positions, deps+packaging (pyyaml/pyproject), empty-legal-moves skip, barrier mechanics, CLI `__main__`, and illegal-move/barrier tests. Step 1 stays 📦, ready for Developer.
- 2026-06-25 — step1 — Developer session: implemented all A–G boxes, 26 tests pass, `python -m src.game` runs 6 sub-games. Step 1 → ✅.
