<!--
  PRD template — the WHAT & WHY. Built by the BUILDER session from the DECISION doc.
  Save as: docs/stepN_<slug>/PRD_stepN_<slug>.md
-->

# PRD — Step <N>: <STEP NAME>

- **Status:** triplet-built
- **Source:** `DECISION_stepN_<slug>.md`
- **Assignment references:** <PDF §§>

## 1. Problem & context
<Why this step exists; where it sits in the Cop-and-Thief / MCP architecture.>

## 2. Goal & success metric
<The single outcome this step must achieve, stated measurably.>

## 3. Stories
<!-- Frame as system/agent stories, not end-user. -->
- As the **<game engine / Cop agent / Thief agent / orchestrator>**, I need <...> so that <...>.

## 4. Functional requirements
<!-- Numbered, testable, no implementation detail. -->
- **FR1** — <requirement>
- **FR2** — <requirement>

## 5. Non-functional requirements
- **NFR1 — config-driven:** all parameters read from `config.yaml` (no hard-coding).
- **NFR2 — resizable:** no assumption of a fixed grid size.
- <NFR3 — performance / security / logging as relevant>

## 6. In scope / Out of scope
**In scope:** <...>
**Out of scope:** <... → step M>

## 7. Acceptance criteria
<!-- Copy & sharpen from DECISION §8. These gate "step done". -->
1. <criterion + how it's verified>
2. <criterion + how it's verified>

## 8. Dependencies
- **Upstream (needs):** step <M> — <what>
- **Downstream (unblocks):** step <K> — <what>

## 9. References
- Assignment §<...>; `DECISION_stepN_<slug>.md`; `config.yaml` keys: <...>
