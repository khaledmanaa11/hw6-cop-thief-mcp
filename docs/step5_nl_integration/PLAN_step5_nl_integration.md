# PLAN — Step 5: Natural-Language Integration (LLM agents)

- **Status:** triplet-built
- **Source:** `DECISION_step5_nl_integration.md`, `SDK_REFERENCE_anthropic.md`, `PRD_step5_nl_integration.md`
- **Cross-links:** `PRD_step5_nl_integration.md` (requirements) · `TODO_step5_nl_integration.md` (atomic build order)

## 1. Architecture (C4 / the new seam)
Step 5 adds a client-side **agent tier** above the existing Step 4 strategy tier. The MCP servers still
validate moves and accept message envelopes; they do not run prompts, call Anthropic, store beliefs, or
own game state. The referee remains the owner of the true `GameState`. Each agent receives only a
projection (`observe`) plus an inbox, then returns one `AgentAction`.

```
 python -m src.orchestrator
        |
        v
  build_agent(role, config, llm_client)  ---- src/agents/factory.py
        |
        +--> LLMAgent(role, config, llm_client, MinimaxMover)
        |       render observation + inbox
        |       call LLMClient.complete(system, user, OUTPUT_SCHEMA)
        |       parse move/message/belief/reasoning
        |       build belief GameState
        |       minimax/evaluate veto
        |       return AgentAction
        |
        +--> MoverAgent(build_mover(role, config))
                legacy greedy|minimax|qtable|random compatibility

  referee.run_sub_game
        |
        +--> observe(state, side, mode, params, inbox)  ---- partial Dec-POMDP view
        +--> agent.act(observation, inbox)
        +--> gateway.validate_move(...)                 ---- unchanged MCP validation
        +--> apply_move(state, action.move)
        +--> gateway.send_message({from, turn, ts, text})
        +--> append envelope to opponent inbox
        +--> ReplayLog.write(richer JSONL record)
```

The new seam is `Agent.act(observation, inbox) -> AgentAction`. Existing movers remain usable through
`MoverAgent`, so old tests and older orchestration paths can still supply `GreedyMover`, `MinimaxMover`,
`QTableMover`, or `RandomMover`.

## 2. File / module layout
```
src/agents/__init__.py              (new)   — export Agent, AgentAction, LLMAgent, MoverAgent, LLMClient, AnthropicLLM, FakeLLM, build_agent
src/agents/llm_client.py            (new)   — LLMClient protocol, AnthropicLLM verified SDK call, FakeLLM deterministic double
src/agents/prompts.py               (new)   — OUTPUT_SCHEMA, THE DETECTIVE/THE GHOST system prompts, render_observation
src/agents/agent.py                 (new)   — Agent protocol, AgentAction, LLMAgent hybrid loop, MoverAgent adapter
src/agents/factory.py               (new)   — build_agent(role, config, llm_client) -> Agent
src/game/config.py                  (edit)  — add trailing-optional agents and observation fields/defaults
config.yaml                         (edit)  — append agents: and observation: blocks, no secrets
src/orchestrator/recorders.py       (edit)  — observe blind|noisy|full, Telemetry LLM samples, belief error helper
src/orchestrator/referee.py         (edit)  — Agent driver, inbox message bus, richer JSONL records
src/orchestrator/__main__.py        (edit)  — build configured agents and AnthropicLLM for live runs; keep manual server boot flow
tests/test_agents/__init__.py       (new)   — test package marker
tests/test_agents/test_llm_client.py(new)   — FakeLLM shape, no real API, telemetry metadata
tests/test_agents/test_prompts.py   (new)   — schema, persona text, cache_control, blind prompt leak guard
tests/test_agents/test_agent.py     (new)   — LLMAgent parse/belief/veto, MoverAgent compatibility
tests/test_agents/test_observe.py   (new)   — blind/noisy/full projections
tests/test_agents/test_referee.py   (new)   — NL bus, replay fields, reasoning privacy, 3x3 InMemoryGateway series
tests/test_agents/test_config.py    (new)   — config defaults and yaml parsing
tests/test_agents/test_doctrine.py  (new)   — honest vs liar belief error, confidence regime
```

`src/mcp_servers/` is intentionally absent from the edit list.

## 3. Data model / key structures
- **`LLMClient`** — protocol:
  `complete(system: list[dict], user: str, schema: dict) -> dict`. The returned dict contains the
  structured output fields plus optional client-side `_llm` telemetry metadata.
- **`Agent`** — protocol:
  `act(self, observation: dict, inbox: list[dict]) -> AgentAction`.
- **`AgentAction`** — dataclass:
  `move: Move`, `message: str`, `belief: tuple[int, int] | None`, `confidence: str`, `intent: str`,
  `reasoning: str`, `llm: dict`.
- **`OUTPUT_SCHEMA`** — structured-output JSON schema with required fields:
  `opponent_guess`, `confidence`, `move`, `message`, `intent`, `reasoning`, and
  `additionalProperties: False`.
- **Observation dict** — produced by `observe()`:
  `role`, `self`, `grid`, `barriers`, `moves_used`, `moves_left`, `cop_barriers_left`,
  `sees_opponent`, `opponent_pos`, `opponent_hint`, `inbox`, `last_msg`.
- **Inbox** — referee-owned:
  `{"COP": [envelopes...], "THIEF": [envelopes...]}`. A message from `COP` is appended only to
  `THIEF`'s inbox, and vice versa.
- **Message envelope** — unchanged server-facing shape:
  `{from, turn, ts, text}`. No coordinate fields, belief fields, move fields, or reasoning fields.
- **Replay ply record** — Step 3 record plus:
  `action.message`, `action.belief`, `action.belief_error`, `action.confidence`, `action.intent`,
  `action.reasoning`, `action.llm`; observations for both sides remain present.

## 4. Component design

### `src/agents/llm_client.py`
- **Responsibility:** hide real Anthropic SDK details behind an injectable seam and provide a free,
  deterministic test double.
- **Key functions/classes:**
  - `class LLMClient(Protocol): complete(system, user, schema) -> dict`
  - `class AnthropicLLM`: constructor receives `model`, `max_tokens`, `temperature`; reads
    `ANTHROPIC_API_KEY` implicitly via `anthropic.Anthropic()`.
  - `AnthropicLLM.complete(...)`: uses exactly the verified call shape:
    `client.messages.create(model=self.model, max_tokens=self.max_tokens, output_config={"format":
    {"type": "json_schema", "schema": schema}}, system=system, messages=[...])`, with temperature
    only when configured for a model that supports it. Parse the first text block with `json.loads`.
  - `class FakeLLM`: returns the same dict shape, supports scripted responses, and has deterministic
    `honest` / `liar` personas for doctrine tests.

### `src/agents/prompts.py`
- **Responsibility:** centralize structured schema and prompt rendering.
- **Key functions/classes:**
  - `OUTPUT_SCHEMA: dict` — exactly matches SDK reference, including `additionalProperties: False`.
  - `system_prompt(role: str, config) -> list[dict]` — returns one cacheable text block with
    `cache_control: {"type": "ephemeral"}`. The Cop block is THE DETECTIVE; the Thief block is
    THE GHOST. Both enforce "truth only in `reasoning`, taunts/deception only in `message`."
  - `render_observation(observation: dict, inbox: list[dict]) -> str` — renders the per-ply user turn
    with role, self position, grid, barriers, mode hint, conversation history, and legal move names.

### `src/agents/agent.py`
- **Responsibility:** implement the hybrid LLM+minimax action loop and legacy mover adapter.
- **Key functions/classes:**
  - `class Agent(Protocol): act(...) -> AgentAction`
  - `class MoverAgent`: wraps any Step 4 `Mover`; expects full truth in observation; emits a stub
    compatibility message only when legacy movers are explicitly selected.
  - `class LLMAgent`: owns role, config, injected `LLMClient`, and a Step 4 `MinimaxMover`.
  - `LLMAgent.act(...)` sequence:
    1. add legal move names to an observation copy;
    2. call `system_prompt` and `render_observation`;
    3. call `llm.complete(..., OUTPUT_SCHEMA)`;
    4. validate/sanitize `opponent_guess`, `confidence`, `move`, `message`, `intent`, `reasoning`;
    5. build a belief `GameState`;
    6. compute minimax best move and proposed-vs-best value gap on the belief state;
    7. veto illegal/lethal/prohibitively bad proposals using the confidence-weighted margin;
    8. return `AgentAction`.

### `src/agents/factory.py`
- **Responsibility:** one construction entry point for live and test orchestrators.
- **Key function:** `build_agent(role: str, config, llm_client: LLMClient | None = None) -> Agent`.
  `"llm"` returns `LLMAgent`; `greedy|minimax|qtable|random` returns `MoverAgent(build_mover(...))`
  through a config proxy that threads the selected name into `config.strategy[role]`.

### `src/orchestrator/recorders.py`
- **Responsibility:** partial observation, replay helpers, and telemetry aggregation.
- **Key changes:**
  - preserve old `observe(state, side, last_msg=None)` calls by defaulting to `full`;
  - add keyword-only `mode`, `params`, `inbox`;
  - add `chebyshev_error(guess, truth) -> int | None`;
  - extend `Telemetry` with `record_llm(sample: dict)` and LLM summary fields.

### `src/orchestrator/referee.py`
- **Responsibility:** drive `Agent`s, maintain inboxes, validate moves through MCP, and record rich plies.
- **Key changes:**
  - keep `run_sub_game` / `run_series` signatures compatible;
  - wrap legacy movers with `MoverAgent` if an object lacks `act`;
  - allow `run_series` inputs to be either existing mover/agent objects or callables that receive a
    runtime role and return a role-specific agent, so the §4.4 role-swap still gets the correct
    DETECTIVE/GHOST prompt each sub-game;
  - call `observe(... mode=config.observation["mode"], params={**config.observation, "max_moves":
    config.max_moves}, inbox=inboxes[side])`;
  - send exactly `{"from": side, "turn": state.moves_used, "ts": ..., "text": action.message}`;
  - never place `reasoning` in the envelope;
  - record belief and telemetry in JSONL.

## 5. Control flow / sequences
1. `python -m src.orchestrator` loads `config.yaml`.
2. It constructs `Telemetry`, `HttpGateway`s, and pings both MCP servers as in Step 3.
3. It constructs one `AnthropicLLM` from `config.agents.llm` when either role is configured as `llm`.
4. It passes group factories into `run_series`, for example
   `lambda runtime_role: build_agent(runtime_role.lower(), config, llm_client)`, so each sub-game's
   Cop gets THE DETECTIVE prompt and each Thief gets THE GHOST prompt even when group A/B swap roles.
5. `run_series` alternates roles by sub-game exactly as before.
6. In each ply, `run_sub_game` selects the active side and builds that side's partial observation and
   inbox.
7. `LLMAgent.act` renders prompt, calls the LLM seam, builds a belief state, applies the veto, and
   returns `AgentAction`.
8. Referee validates `action.move.name` through the active side's `ServerGateway.validate_move`.
9. Referee applies the move to true state with `apply_move`.
10. Referee sends the opponent-visible envelope through `gateway.send_message` and appends it to the
   other side's inbox.
11. Referee writes the richer JSONL ply record and continues until capture or timeout.

## 6. Config additions
| Key | Default | Used by |
|-----|---------|---------|
| `agents.cop` | `llm` | `build_agent("cop", ...)` |
| `agents.thief` | `llm` | `build_agent("thief", ...)` |
| `agents.llm.provider` | `anthropic` | `src/orchestrator/__main__.py`, `AnthropicLLM` construction |
| `agents.llm.model` | `claude-haiku-4-5-20251001` | `AnthropicLLM`; default lives in YAML/config, not source literals |
| `agents.llm.max_tokens` | `1024` | `AnthropicLLM.complete` |
| `agents.llm.temperature` | `0.7` | `AnthropicLLM.complete` for Haiku 4.5; omit for unsupported models |
| `agents.llm.veto_margin` | `50.0` | `LLMAgent` confidence-weighted veto |
| `observation.mode` | `noisy` | `recorders.observe`, referee |
| `observation.noisy.reveal_radius` | `2` | noisy exact-reveal threshold |
| `observation.noisy.quadrant_hint` | `true` | noisy coarse-region hint |

Both blocks are trailing optional in `Config`; absent blocks get the defaults above.

## 7. Test strategy
- **Unit:** `FakeLLM` response shape, Anthropic call assembly with monkeypatch (no network), schema
  validity, persona text, prompt cache block, blind prompt leak guard, observation projections, belief
  error helper, `LLMAgent` parse/veto paths.
- **Integration:** `run_sub_game` and `run_series` with `InMemoryGateway` + `FakeLLM`; message envelope
  delivery; replay JSONL fields; telemetry sample count; `MoverAgent` compatibility.
- **Sanity-grid escalation:** at minimum one full `FakeLLM` series on 3x3; existing Step 1-4 tests cover
  2x2-5x5 game/strategy behavior. Step 5 agent code must not contain fixed grid literals.
- **Live manual:** not run in tests. With servers running and key set, run `python -m src.orchestrator`
  and inspect transcript/replay/telemetry.

## 8. Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM prompt leaks hidden coordinates in blind/noisy mode | Medium | `observe` projection tests plus prompt text grep for true coordinate in blind mode |
| SDK call shape drifts or is guessed wrong | Medium | Copy `SDK_REFERENCE_anthropic.md`; test call assembly via monkeypatch, no live API in tests |
| Real LLM returns bad JSON or invalid move | High | Structured output schema, parse validation, illegal-move minimax veto |
| Minimax veto fully replaces LLM | Medium | Confidence-weighted margin and tests proving good proposals are kept |
| Legacy tests break because referee expects `Agent` | Medium | `_ensure_agent` / `MoverAgent` compatibility path and old mover tests stay valid |
| Prompt caching silently absent in tests | High for tiny prompts | Only assert `cache_control` is sent, not cache-creation token count |
| Telemetry cost estimate wrong | Low | Use approximate Haiku 4.5 pricing from SDK reference and label as estimated |
| API key accidentally committed | Low | `AnthropicLLM` uses env via SDK; tests grep for secrets/defaults |

## 9. Work breakdown (macro order)
1. Add config defaults and `src/agents/` scaffolding.
2. Implement `llm_client.py` from the verified SDK reference and deterministic `FakeLLM`.
3. Implement prompts, schema, persona doctrine, and render function.
4. Implement `LLMAgent`, belief-state builder, confidence-weighted minimax veto, and `MoverAgent`.
5. Upgrade `observe`, telemetry, referee inbox routing, replay records, and orchestrator construction.
6. Add `tests/test_agents/` covering all PRD acceptance criteria and doctrine hooks.
7. Run targeted checks and the full suite in the Developer session only.
