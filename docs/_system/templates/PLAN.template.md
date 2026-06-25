<!--
  PLAN template — the HOW. Built by the BUILDER session from the DECISION doc.
  This is the architecture/design that the TODO will turn into atomic boxes.
  Save as: docs/stepN_<slug>/PLAN_stepN_<slug>.md
-->

# PLAN — Step <N>: <STEP NAME>

- **Status:** triplet-built
- **Source:** `DECISION_stepN_<slug>.md`, `PRD_stepN_<slug>.md`

## 1. Architecture overview
<Where this step's code sits in the system; a small diagram or flow if useful.>

## 2. File / module layout
<!-- Tree of files to CREATE or MODIFY. Mark each. -->
```
<path/to/new_file.py>        (new)   — <responsibility>
<path/to/existing.py>        (edit)  — <what changes>
config.yaml                  (edit)  — <keys added>
tests/<test_file.py>         (new)   — <what it covers>
```

## 3. Data model / key structures
<!-- Names, fields, types. The TODO will reference these exactly. -->
- `<TypeName>` — <fields: type — meaning>

## 4. Component design
<!-- One block per module. Give signatures + behavior. -->
### `<module/class>`
- **Responsibility:** <...>
- **Key functions:**
  - `def <name>(<args: types>) -> <return>:` — <behavior, edge cases>

## 5. Control flow / sequences
<Step-by-step of the important flow, e.g. one move of a sub-game, or one tool call.>

## 6. Config additions
| Key | Default | Used by |
|-----|---------|---------|
| `<key>` | `<default>` | <module> |

## 7. Test strategy
- **Unit:** <what>
- **Integration:** <what>
- **Sanity-grid escalation:** how this step is checked at 2×2 → 3×3 → 4×4 → 5×5 (where relevant).

## 8. Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| <...> | <...> | <...> |

## 9. Work breakdown (macro order)
<!-- The big chunks, in order. The TODO breaks each into atomic boxes. -->
1. <chunk> 2. <chunk> 3. <tests> 4. <wiring>
