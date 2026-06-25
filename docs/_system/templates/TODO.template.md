<!--
  TODO template — the DO IT list. Built by the BUILDER session from DECISION + PLAN.
  THIS IS THE MOST IMPORTANT FILE. It is handed to a WEAK MODEL with no other context.
  Make it FAT: many small, atomic, unambiguous boxes. Each box = one self-contained edit.
  Save as: docs/stepN_<slug>/TODO_stepN_<slug>.md
-->

# TODO — Step <N>: <STEP NAME>

> Implements `PRD_stepN_<slug>.md` + `PLAN_stepN_<slug>.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename.
3. **Never hard-code** game parameters — read them from `config.yaml`.
4. Do not assume a 5×5 grid; read `grid_size` from config.
5. If a box seems ambiguous, STOP and ask — do not guess.
6. Keep each file focused; do not add features not listed here.

## Conventions
- Language/runtime: <e.g. Python 3.11, uv, pytest>
- Source root: `<src/>` · Tests: `<tests/>`
- Each box format: **ID · file · action · detail · Check.**

---

## Phase A — <setup / scaffolding>
- [ ] **A1** — `<path>` — <create/modify> — <exact change: signatures, types, behavior>.
      **Check:** <command or observable result, e.g. `python -c "import x"` runs clean>.
- [ ] **A2** — `<path>` — <action> — <detail>.
      **Check:** <...>

## Phase B — <core logic>
- [ ] **B1** — `<path>` — <action> — <detail incl. exact function signature>.
      **Check:** <...>
- [ ] **B2** — ...
<!-- Keep going. Aim for MANY small boxes (often 20–60 for a real step), not a few big ones. -->

## Phase C — <tests>
- [ ] **C1** — `tests/<file>` — create test `<name>` asserting <behavior>.
      **Check:** `pytest tests/<file>::<name>` passes.

## Phase D — <wiring / config / integration>
- [ ] **D1** — `config.yaml` — add keys <...> with defaults <...>.
      **Check:** loader returns the values.

---

## Definition of Done
- [ ] Every box above is ticked and its Check passed.
- [ ] All PRD acceptance criteria hold (`PRD_stepN_<slug>.md` §7).
- [ ] No hard-coded game parameters anywhere in the step's code.
- [ ] Update `docs/_system/ROADMAP.md`: set step <N> to ✅ and add a progress-log line.
