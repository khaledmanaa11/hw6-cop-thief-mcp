<!--
  DECISION template — output of a PLANNER session (Session A).
  This is the self-contained handoff doc. The Builder session must need NOTHING
  but this file. Replace every <PLACEHOLDER>; delete instructional comments.
  Save as: docs/stepN_<slug>/DECISION_stepN_<slug>.md
-->

# DECISION — Step <N>: <STEP NAME>

- **Roadmap position:** step <N> of 8 (`<slug>`)
- **Date discussed:** <YYYY-MM-DD>
- **Status:** decision-written
- **Assignment references:** <PDF §§ that bind this step, e.g. §4.1–4.4, §10>

## 1. What this step is (one paragraph)
<Plain-language statement of the step's purpose.>

## 2. What it adds to the project
<!-- The "after this step, the project HAS X" list. Be concrete. -->
- <new capability / module / file 1>
- <new capability / module / file 2>

## 3. Scope
**In scope:**
- <...>

**Out of scope (deferred):**
- <thing> → handled in step <M>

## 4. Chosen approach (and what we rejected)
**Decision:** <the approach we picked>

**Why:** <reasoning>

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| <option A> | ✅ chosen | <...> |
| <option B> | ❌ rejected | <...> |

## 5. Dependencies & interfaces
- **Consumes from prior steps:** <modules/contracts this relies on>
- **Exposes to later steps:** <the API/contract later steps will use>
- **Touches config keys:** <grid_size, ... or "none">

## 6. Binding constraints (from the assignment)
<!-- Pull only the rules that actually constrain THIS step. -->
- <e.g. board must be resizable — no hard-coded 5×5>
- <e.g. LLM lives in client, not MCP server>

## 7. Key design decisions
<!-- High-level only; the PLAN doc expands these. Include intended files & shapes. -->
- **Files/modules:** <paths to create/change>
- **Core data structures:** <names + rough shape>
- **Key signatures (intent):** <function/class names + one-line behavior>

## 8. Acceptance criteria (how we know the step is done)
1. <testable criterion>
2. <testable criterion>

## 9. Resolved questions / open items
- **Q:** <question> → **A:** <answer decided with Director>
- **Still open (note for Builder):** <anything, or "none">

## 10. Notes for the Builder session
<Any emphasis: where to put the most TODO detail, naming, gotchas.>
