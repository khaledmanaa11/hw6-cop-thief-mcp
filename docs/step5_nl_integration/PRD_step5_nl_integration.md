# PRD — Step 5: Natural-Language Integration (LLM agents)

| Field | Value |
|-------|-------|
| Component | `step5_nl_integration` (client-tier natural-language agents) |
| Version | 1.00 |
| Depends on | Step 1 (`src/game/`), Step 3 (`src/orchestrator/`, MCP gateways), Step 4 (`src/strategy/`) |

- **Status:** triplet-built — awaiting Director approval before any code
- **Source:** `DECISION_step5_nl_integration.md`; SDK ground truth: `SDK_REFERENCE_anthropic.md`
- **Cross-links:** `PLAN_step5_nl_integration.md` (architecture) · `TODO_step5_nl_integration.md` (atomic build order)
- **Assignment references:** §2 / §3 (graded value = agent communication and orchestration, not the move algorithm); §5 / §5.2 (server/client split: LLM in the client, MCP servers expose tools only); §4.1-§4.4 (game rules, scoring, role swap unchanged); standing constraints from `docs/_system/WORKFLOW.md` §6 (free natural language, no hard-coding, resizable board, Dec-POMDP model).

## 1. Problem & context
Steps 1-4 produced a valid distributed Cop-and-Thief game: rules are enforced by the engine, MCP
servers validate actions, the orchestrator runs a role-swapped series, and Step 4 supplies real
strategy movers. But the "conversation" is still a stub: the referee emits `"<side> plays <move>"`
and `recorders.observe()` gives each side full ground truth. That means the agents do not need
language; they already see the opponent.

Step 5 makes natural-language communication load-bearing. The Cop and Thief become client-tier
LLM agents. On each ply, the active agent receives a partial observation plus its inbox, infers a
belief about the opponent, emits one free-text message, and proposes a move. The Step 4 minimax
brain remains as a safety floor: it vetoes illegal or clearly losing proposals, but does not replace
the LLM's role in belief, messaging, and move intent. The MCP servers stay validate-only.

## 2. Goal & success metric
After this step, `python -m src.orchestrator` can run a full `num_games` series with both roles driven
by LLM-backed `Agent`s. Each ply contains a genuine free-text message, a logged private belief, LLM
telemetry, and a partial observation that does not leak hidden coordinates outside the selected
observation mode.

Success is measured by:
- live manual run with both MCP servers and `ANTHROPIC_API_KEY` set: full series completes, transcript
  contains varied non-stub natural language, and group totals remain in the §4.4 `[30, 90]` band;
- offline tests use only `FakeLLM`, require no key or network, and cover the 3x3 resizability case;
- replay JSONL records enough message, belief, and telemetry data to explain the Dec-POMDP story later.

## 3. Stories
- As the **Cop agent**, I need to read only my own partial observation and the Thief's messages so
  that I must interrogate, distrust, and infer instead of reading ground truth.
- As the **Thief agent**, I need to send deceptive natural language while privately tracking my real
  belief so that survival depends on corrupting the Cop's belief rather than exposing my position.
- As the **orchestrator**, I need one `Agent` protocol for both LLM agents and legacy movers so that
  Step 5 can add natural language without breaking the existing series runner.
- As the **record/replay layer**, I need each ply to include outgoing message, private reasoning,
  inferred belief, belief error, and LLM telemetry so that a nondeterministic live run is still
  auditable from its JSONL transcript.
- As the **grader / README author**, I need concrete Dec-POMDP evidence (`Ωᵢ`, `O`, belief error,
  deception doctrine) so that the project's graded core is visible, testable, and explainable.

## 4. Functional requirements
- **FR-NL1 — Client-tier `src/agents/` package.** Add `llm_client.py`, `agent.py`, `prompts.py`,
  `factory.py`, and `__init__.py`. No LLM logic enters `src/mcp_servers/`.
- **FR-NL2 — Injectable LLM seam.** Define an `LLMClient` protocol with
  `complete(system, user, schema) -> dict`. Implement `AnthropicLLM` using the verified SDK shape from
  `SDK_REFERENCE_anthropic.md`, and `FakeLLM` as a deterministic, scriptable test double returning the
  same dict shape.
- **FR-NL3 — Structured per-ply LLM output.** Every LLM response must match:
  `opponent_guess`, `confidence`, `move`, `message`, `intent`, `reasoning`. `message` is the only
  opponent-visible field; `reasoning` is private and logged only.
- **FR-NL4 — Locked personas and two-channel discipline.** `prompts.py` encodes THE DETECTIVE (Cop)
  and THE GHOST (Thief): cold truth only in private `reasoning`, adversarial taunts and deception only
  in `message`. Both prompts must apply level-2 reasoning: model what the opponent believes, then
  corrupt or exploit that belief.
- **FR-NL5 — Hybrid `LLMAgent.act`.** `LLMAgent` renders observation+inbox, calls the injected
  `LLMClient`, parses the structured dict, builds a belief `GameState`, compares the proposed move
  against Step 4 minimax/evaluation, vetoes illegal or clearly losing moves, and returns an `AgentAction`.
- **FR-NL6 — Confidence-weighted minimax veto.** Effective veto margin is
  `veto_margin * {"low": 0.3, "medium": 1.0, "high": 3.0}[confidence]`. Low confidence lets minimax
  dominate; high confidence lets the LLM keep more proposals. A Cop `PLACE_BARRIER` with
  `intent == "trap"` is exempt from the eval-veto but still must be legal.
- **FR-NL7 — Backward-compatible `MoverAgent`.** Existing Step 3/4 movers keep working by wrapping
  `choose_move(state) -> Move` objects in an `Agent`. Existing tests and series calls must not need a
  rewrite to stay green.
- **FR-NL8 — Partial observations.** Extend `recorders.observe()` to support config modes
  `blind | noisy | full`. `blind` never exposes opponent coordinates; `noisy` exposes exact opponent
  position only within `reveal_radius`, otherwise a coarse region hint; `full` preserves Step 3 behavior.
- **FR-NL9 — Real message bus.** The referee routes the active agent's authored message into the
  opponent's inbox using the existing `{from, turn, ts, text}` envelope. The envelope must not gain
  coordinate fields or structured protocol fields.
- **FR-NL10 — Rich replay and telemetry.** Every ply record includes `message`, `belief`,
  `belief_error` (Chebyshev distance to truth), `reasoning`, `intent`, `confidence`, and `llm`
  telemetry. End-of-run telemetry summarizes LLM call count, average latency, total tokens, cache tokens,
  and estimated cost.
- **FR-NL11 — Config-driven agent selection.** Add trailing-optional `agents:` and `observation:`
  blocks to `config.yaml` and `Config`. Defaults select LLM agents with Anthropic Haiku 4.5 and `noisy`
  observation. Existing positional `Config(...)` construction remains valid.
- **FR-NL12 — Offline tests only.** Tests under `tests/test_agents/` must use `FakeLLM` and
  `InMemoryGateway`; no test calls Anthropic, requires `ANTHROPIC_API_KEY`, or opens real sockets.

## 5. Non-functional requirements
- **NFR1 — config-driven:** model, provider, max tokens, temperature, veto margin, observation mode,
  and reveal radius come from `config.yaml`; API key comes from `ANTHROPIC_API_KEY`.
- **NFR2 — resizable:** no 5x5 assumption. Agent code derives bounds from observations/config and is
  proven on a 3x3 end-to-end test.
- **NFR3 — no secrets:** no API key in config, code, docs examples, tests, replay, or telemetry.
- **NFR4 — no server contamination:** `src/mcp_servers/` remains validate-only and unchanged by this step.
- **NFR5 — replay honesty:** live LLM nondeterminism is accepted; reproducibility comes from JSONL logs
  and deterministic `FakeLLM` tests.
- **NFR6 — SDK correctness:** `AnthropicLLM` uses the verified `messages.create` call shape with
  `output_config={"format": {"type": "json_schema", "schema": SCHEMA}}`, system prompt caching, and
  `resp.usage` telemetry.
- **NFR7 — prompt safety by channel:** true state, deductions, and plans must live in `reasoning`;
  opponent-visible `message` is adversarial free text and never a status report.

## 6. In scope / Out of scope
**In scope:** `src/agents/`; `recorders.observe()` modes; referee `Agent` driver and natural-language
message routing; config additions; richer replay/telemetry; `tests/test_agents/` using `FakeLLM`;
manual live-run support through `python -m src.orchestrator`.

**Out of scope:** GUI rendering (Step 6); cloud deployment/secrets hygiene beyond env-var use (Step 7);
JSON-only Gmail report (Step 8); any game-rule, scoring, movement, barrier, or MCP server tool-contract
change; fine-tuning, embeddings, RAG, or training an LLM.

## 7. Acceptance criteria
1. **Live LLM series:** with both MCP servers manually started and a valid `ANTHROPIC_API_KEY`,
   `python -m src.orchestrator` plays a full `num_games` series where each ply's move and free-text
   message are produced by an LLM agent; transcript messages are varied and not the old
   `"<side> plays <move>"` stub; `SeriesResult` totals are in `[30, 90]`.
2. **Partial observation modes:** tests assert `blind` has `opponent_pos is None` and
   `sees_opponent is False`; `noisy` reveals exact position only within `reveal_radius` and otherwise
   emits a coarse hint; `full` returns the true position.
3. **Real NL channel:** tests assert the active agent emits a non-stub `{from, turn, ts, text}` envelope
   with no coordinate fields, the gateway accepts it, and the opponent's next observation includes it.
4. **Hybrid veto:** tests assert an illegal/blunder `FakeLLM` proposal is overridden by minimax and a
   good proposal is kept.
5. **Belief logged and scored:** every ply records `belief` and Chebyshev `belief_error`; tests assert
   correctness against a known `FakeLLM` guess.
6. **No network in tests:** all `tests/test_agents/` tests use `FakeLLM` with no key; an end-to-end
   series runs on `InMemoryGateway` + `FakeLLM`, including a 3x3 config.
7. **Backward compatibility:** existing tests still pass; legacy movers run through `MoverAgent` or the
   compatibility path unchanged.
8. **Config-driven / no hard-coding / no secrets:** model, observation, reveal radius, and veto margin
   come from config; grep of `src/agents/` finds no default model literal, no API key, and no fixed grid
   constants.
9. **LLM telemetry:** end-of-run summary reports LLM call count, average latency, total tokens, cache
   tokens, and estimated cost; tests assert one LLM telemetry sample per agent decision via `FakeLLM`.
10. **Prompt caching:** the static rules/persona system prompt is sent as a list block with
    `cache_control: {"type": "ephemeral"}`; the PRD and TODO document the Haiku 4.5 cache minimum and
    do not assert cache writes for tiny test prompts.
11. **Doctrine hook — deception metric:** deterministic `FakeLLM` honest and liar/decoy personas prove
    that belief error is materially higher against the liar than the honest persona.
12. **Doctrine hook — private reasoning:** tests assert `reasoning` is recorded in JSONL but never
    appears in any `send_message` envelope `text`.
13. **Doctrine hook — confidence regime:** tests assert low-confidence proposals are vetoed more often
    than high-confidence proposals for the same board and candidate move quality.

## 8. Dependencies
- **Upstream (needs):** Step 1 `GameState`, `Board`, `Move`, `legal_moves`, `apply_move`,
  `initial_state`, `is_capture`, `is_timeout`, `score_sub_game`; Step 3 `ServerGateway`,
  `InMemoryGateway`, `HttpGateway`, `ReplayLog`, `Telemetry`, `observe`, `render_board`,
  `run_sub_game`, `run_series`, `{from, turn, ts, text}` envelope; Step 4 `MinimaxMover`,
  `evaluate`, and `build_mover`.
- **Downstream (unblocks):** Step 6 GUI/replay reads richer JSONL; Step 7 cloud deployment reuses the
  client-tier `Agent` seam; Step 8 report consumes belief, message, and telemetry metrics.

## 9. References
- `docs/step5_nl_integration/DECISION_step5_nl_integration.md`
- `docs/step5_nl_integration/SDK_REFERENCE_anthropic.md`
- `docs/_system/WORKFLOW.md`
- Config keys added: `agents.*`, `observation.*`
- Existing real signatures verified before writing this triplet: `legal_moves(state)`,
  `apply_move(state, move)`, `GameState`, `MinimaxMover(depth, weights, max_moves=...)`,
  `evaluate(state, config)`, `build_mover(role, config)`, `ServerGateway`, `run_sub_game`,
  `run_series`, `observe`, `ReplayLog`, `Telemetry`

