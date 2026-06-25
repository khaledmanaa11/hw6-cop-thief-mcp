# WORKFLOW — How this project is planned and built

This file defines the **repeatable two-session machine** used to take each roadmap
step from "idea" to "implemented code". It is the operating manual for the whole
`docs/` system. Read this first in every new session.

> Project: **HW6 — Dual AI Agent Conversation via MCP Servers** (Dr. Yoram Segal).
> A Cop-and-Thief pursuit game where two autonomous AI agents, each behind its own
> MCP server, play by talking in **free natural language**. The graded value is the
> **orchestration/architecture**, not the game-playing algorithm.

---

## 0. Roles

- **Director** (the human / Khaled) — decides, discusses, approves.
- **Planner session** — an interactive Claude session that discusses ONE roadmap
  step with the Director and writes the `DECISION` doc.
- **Builder session** — a small, cheap Claude session (or subagent) that reads ONLY
  the `DECISION` doc and writes the `PRD + PLAN + TODO` triplet.
- **Developer** (a weak model) — given ONE `TODO_<step>.md`, implements it box by box.

Each role runs in its **own fresh session**. Continuity between sessions lives in
**files** (`docs/`), not in chat memory. The `ROADMAP.md` tracker is the index that
tells any new session where we are.

---

## 1. The pipeline (per roadmap step)

```
                 ┌─────────────────────┐
  Roadmap step → │  SESSION A: Planner │  (interactive, with the Director)
                 │  discuss + decide   │
                 └──────────┬──────────┘
                            │ writes
                            ▼
              docs/stepN_<slug>/DECISION_stepN_<slug>.md
                            │ (self-contained — the ONLY input below)
                            ▼
                 ┌─────────────────────┐
                 │ SESSION B: Builder  │  (small / subagent)
                 │ expand to triplet   │
                 └──────────┬──────────┘
                            │ writes
                            ▼
       PRD_stepN_<slug>.md · PLAN_stepN_<slug>.md · TODO_stepN_<slug>.md
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Developer (weak LLM)│  implements TODO box-by-box → code
                 └─────────────────────┘
```

**Golden rule:** the `DECISION` doc must be self-contained. The Builder session must
never need to re-read the PDF or the chat — everything it needs is in `DECISION`.
Likewise the `TODO` must be atomic enough that a weak model needs nothing but the
triplet to write correct code.

---

## 2. Session A — Planner (discuss + decide)

**Input:** the roadmap step + this WORKFLOW + `ROADMAP.md` + the `DECISION`/triplet
docs of all PRIOR steps (for interfaces) + the assignment PDF if a constraint check
is needed.

**What happens:**
1. Mark the step `🗣️ discussing` in `ROADMAP.md`.
2. Explain to the Director **exactly what this step is** and **what it adds to the
   project** ("after this step, the project has X").
3. Discuss design options, trade-offs, pick the best approach. Resolve open questions.
4. At the end, write `docs/stepN_<slug>/DECISION_stepN_<slug>.md` from the
   `templates/DECISION.template.md`.
5. Mark the step `📄 decision-written` in `ROADMAP.md`.

**Output:** one file — `DECISION_stepN_<slug>.md`.

## 3. Session B — Builder (expand to triplet)

**Input:** ONLY `DECISION_stepN_<slug>.md` (+ the three templates).

**What happens:**
1. Produce the three docs from their templates, in the SAME folder:
   - `PRD_stepN_<slug>.md`  — the WHAT & WHY (requirements).
   - `PLAN_stepN_<slug>.md` — the HOW (architecture, files, structures, tests).
   - `TODO_stepN_<slug>.md` — the DO IT (long, atomic, weak-model-ready checklist).
2. The `TODO` must be **fat**: many small boxes, each with an exact file path, the
   exact change (with function signatures / types / behavior), and a per-box check.
3. Mark the step `📦 triplet-built` in `ROADMAP.md`.

**Output:** three files — `PRD_…`, `PLAN_…`, `TODO_…`.

## 4. Developer — implement

A weak model is handed ONE `TODO_<step>.md`. It does one box at a time, runs the
box's check, ticks the box, and moves on. When all boxes pass and the PRD acceptance
criteria hold, mark the step `✅ done` in `ROADMAP.md`.

---

## 5. Naming & folder conventions

- One folder per step: `docs/stepN_<slug>/` (e.g. `docs/step1_game_logic/`).
- Files inside, suffixed by the step name:
  - `DECISION_stepN_<slug>.md`
  - `PRD_stepN_<slug>.md`
  - `PLAN_stepN_<slug>.md`
  - `TODO_stepN_<slug>.md`
- The canonical step numbers/slugs are fixed in `ROADMAP.md`. Do not invent new ones.
- The system itself (this folder, `docs/_system/`) is never a "step".

## 6. Hard constraints that bind EVERY step (from the assignment)

Carry these into every DECISION/PRD so no step violates them:
- **No hard-coding** — all game parameters live in `config.yaml`/`config.json`
  (grid_size, max_moves, num_games, max_barriers, scoring.*).
- **Generic/resizable** board — never assume 5×5.
- **Server/Client split** — the LLM lives in the **client/orchestrator**; the **MCP
  server only exposes tools** (FastMCP).
- **Free natural language** between agents — no fixed coordinate protocol (this is the
  graded core; relevant from Step 5 on, but design earlier steps to allow it).
- **Dec-POMDP** is the formal model for the README ⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩.
- **JSON-only email** report at end of a 6-sub-game series (Step 8).

## 7. Definition of "step complete"

A step is `✅ done` when: every `TODO` box is ticked, the box checks pass, and the
PRD's acceptance criteria are met. Then update `ROADMAP.md` and start the next step's
Planner session.
