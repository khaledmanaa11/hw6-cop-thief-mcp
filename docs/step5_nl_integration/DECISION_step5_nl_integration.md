# DECISION — Step 5: Natural-Language Integration (the graded core)

- **Roadmap position:** step 5 of 8 (`step5_nl_integration`)
- **Date discussed:** 2026-06-26
- **Status:** decision-written
- **Assignment references:** §2 / §3 (the **graded value is the agent pair's communication & orchestration**, NOT the move algorithm), §5/§5.2 (server/client split — the **LLM lives in the client**, the MCP server only exposes tools), §4.1–4.4 (game rules / series unchanged), the standing free-natural-language and no-hard-coding constraints (WORKFLOW §6), and the README's required **Dec-POMDP** ⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩ formal model — this is the step that gives ⟨Ωᵢ, O⟩ real content.

## 1. What this step is (one paragraph)
Step 5 makes the agents **actually communicate**. Until now the "messages" are a placeholder — `referee.py` emits `f"{side} plays {move_name}"` and `recorders.observe()` hands each agent the *full* ground truth (`sees_opponent: True`, the real `opponent_pos`), so the agents don't talk and don't need to: they read the world directly. Step 5 puts a **Large Language Model (Claude) in the client/orchestrator tier** and inverts that: each agent receives only a **partial observation** of the board plus the **free-text messages** it has been sent, and it must **infer the opponent's location from natural language** — language the opponent is free to make **deceptive**. Per ply the agent's LLM brain (a) reads its inbox, (b) infers a belief about where the opponent is, (c) writes its own free-text message (which the opponent will read — so the Thief is motivated to mislead and the Cop to triangulate), and (d) **proposes a move**; the tested Step-4 **minimax acts only as a veto** that overrides an illegal or clearly-losing proposal. After this step the project has two autonomous LLM agents conversing in plain language across two networked MCP servers — exactly the §2/§3 graded artifact — with the move strategy (not graded) kept honest by the existing search.

## 2. What it adds to the project
- A new **client-tier agent package** `src/agents/` — the natural-language brain (never inside an MCP server):
  - `llm_client.py` — an injectable `LLMClient` seam with `AnthropicLLM` (real, uses the official `anthropic` SDK) and `FakeLLM` (deterministic test double). Same dependency-injection idea as the Step-3 `ServerGateway`.
  - `agent.py` — `LLMAgent`, the hybrid brain (LLM proposes move + message + belief → minimax veto), plus a thin `Agent` protocol.
  - `prompts.py` — the system prompt (rules + role + "your messages are visible to the opponent") and the per-ply observation/inbox rendering.
  - `factory.py` — `build_agent(role, config, llm_client)` mapping a config name to an `Agent`.
- A **partial-observation upgrade** to `recorders.observe()`: three config-selectable modes — `blind | noisy | full` — replacing the Step-3 "always full visibility". This is the seam Step 3 explicitly reserved (`sees_opponent` / `opponent_pos`).
- A **real message bus**: the orchestrator now routes agent-authored NL between the two agents' inboxes (the `send_message` envelope finally carries genuine free text).
- A **richer replay record**: each JSONL ply line now also stores the agent's outgoing message, its inferred belief, and the LLM telemetry — so a run is replayable from the file even though the LLM itself is nondeterministic.
- A new test package `tests/test_agents/` that exercises everything through `FakeLLM` — **no test ever calls the real API**.

**Creative instrumentation (3 baked-in seams, each a proof not a finished feature — fold into the README):**
- **Belief-accuracy metric** — per ply, record the **Chebyshev error** between the agent's `inferred_opponent_pos` and the ground-truth opponent position. This is a *quantitative* Dec-POMDP result: it shows whether communication actually helps an agent localize its opponent, and whether deception measurably degrades the opponent's belief. A genuinely gradeable insight.
- **LLM telemetry** — extend the Step-3 telemetry to also record per-call **latency, input/output tokens, and estimated cost**; print a summary. Proves the run is really LLM-driven and foreshadows Step 7 (cloud) / Step 8 (report) cost.
- **Prompt caching** — the rules + role system prompt is identical across the ~300 calls in a series; mark it with `cache_control` so the shared prefix is billed at ~0.1× after the first call. A real, documented cost optimisation.

## 3. Scope
**In scope:**
- `LLMAgent` driving **both roles** (Cop = pursue/capture, Thief = evade/survive) behind a single `Agent` protocol; role differs only by the system-prompt goal.
- **Hybrid decision** (Director's call): the LLM proposes `{move, message, opponent_guess}`; the Step-4 `MinimaxMover` evaluates the proposal against the LLM's **inferred belief** and **vetoes** only when the proposal is illegal or worse than minimax's best by a configurable margin (`veto_margin`). The LLM is genuinely part of move selection; minimax is the floor that stops a blunder.
- **Three observation modes**, config-selectable, **all implemented** (Director: keep the choice open):
  - `blind` — agent sees its own position, barriers, grid, turn budget, role, and inbox; **never** the opponent's coordinates (messages are the only opponent signal — strongest Dec-POMDP / "infer location, deceive" claim).
  - `noisy` — `blind` plus a degraded hint: exact opponent position only when Chebyshev distance ≤ `reveal_radius`, otherwise a coarse quadrant/region hint.
  - `full` — Step-3 behaviour (real `opponent_pos`); NL is decorative; useful for debugging and as an upper-bound baseline.
  - **Default `noisy`** (watchable demo); to be re-confirmed during testing.
- **Config-selectable model** (default `claude-haiku-4-5-20251001`); `FakeLLM` (or a cheaper model) for tests/CI. API key read from the **`ANTHROPIC_API_KEY` environment variable** — never in config or code.
- Real **message routing** through the orchestrator into per-agent inboxes; envelopes stay `{from, turn, ts, text}` (free text only).
- **Reproducibility by recording**: live runs log the agent message, belief, and LLM I/O metadata per ply; "replay" = reading the JSONL. The deterministic-run guarantee now lives in the `FakeLLM` unit tests.
- The 3 instrumentation seams above (belief-accuracy, LLM telemetry, prompt caching).
- Backward compatibility: the Step-3/4 movers (`greedy|minimax|qtable|random`) remain usable via a `MoverAgent` adapter so the existing 91 tests keep passing.
- Resizability proven on a small grid (e.g. 3×3) with `FakeLLM`; no hard-coded grid/model literals in `src/agents/`.

**Out of scope (deferred):**
- GUI that *renders* the conversation/board → **Step 6** (it replays the richer JSONL).
- Cloud deployment, public URLs, tokens/secrets hygiene → **Step 7**.
- The JSON-only Gmail report after a series → **Step 8** (it reads the JSONL).
- Any change to game rules, scoring, the server tool contract, or the series role-swap (§4.4) — **unchanged**.
- Fine-tuning / training an LLM, embeddings, RAG — not needed; this is prompt-driven inference only.

## 4. Chosen approach (and what we rejected)
**Decision:** A **client-tier `LLMAgent`** behind a unified `Agent` seam. Per ply it calls Claude (structured output) for `{move, message, opponent_guess}` from a **partial observation + inbox**; the Step-4 **minimax vetoes** an illegal or clearly-losing move using the LLM's inferred belief. The LLM lives only in the client; the MCP servers stay validate-only and untouched. The LLM is injected through an `LLMClient` seam so tests run against a `FakeLLM`.

**Why:** The assignment is explicit that **communication/orchestration is graded and the move algorithm is not** (§2/§3). The hybrid keeps the *new, graded* contribution — natural-language messaging, location inference, and deception — squarely in the LLM layer, while the move quality is backstopped by the already-tested search so a demo never collapses into random flailing. Putting the LLM behind the same kind of injection seam the gateway uses keeps the whole thing testable offline (no API key, no network, deterministic). Partial observation is what makes the NL channel *load-bearing* rather than decorative — without it there is nothing to infer and no reason to deceive.

| Option considered | Verdict | Reason |
|-------------------|---------|--------|
| Hybrid: LLM proposes move+message+belief, minimax vetoes | ✅ chosen (Director) | LLM genuinely drives the choice; search prevents blunders; clean to grade and explain |
| LLM decides the move outright | ❌ rejected | Weaker play, more cost/latency, illegal-move retry loops against the server, harder to grade objectively |
| LLM only messages/infers; minimax always moves | ❌ rejected by Director | Wanted the LLM to be part of the move choice, not just a chat layer |
| LLM in the client tier | ✅ chosen | Assignment mandates server/client split; the `Mover`/`Agent` seam is here |
| LLM tool exposed by the MCP server | ❌ rejected | Violates §5.2 (server = tools only); contradicts Steps 2–4 |
| Partial observation (`blind`/`noisy`), config-selectable | ✅ chosen | Makes messages the real sensor; richest Dec-POMDP/deception story; keep both modes open |
| Keep full visibility, NL as flavour | ❌ rejected (kept as `full` debug mode only) | NL channel would be decorative — weakest "infer location, deceive" grade case |
| Default model `claude-haiku-4-5-20251001`, `FakeLLM` in tests | ✅ chosen (Director, 2026-06-27) | No inter-group competition this run, so deception quality need not be maxed — Haiku is far cheaper/faster across the ~300 calls/series and is plenty for the demo. Model stays config-selectable, so a future competitive run can swap to Opus by editing one config line. Tests stay free, fast, deterministic on `FakeLLM`. |
| Record real LLM I/O; replay = read the log | ✅ chosen (Director) | Honest for nondeterministic LLMs; determinism guarantee moves to `FakeLLM` tests |
| Force byte-identical determinism on live runs | ❌ rejected | Not achievable with a real LLM; the recorded transcript is the reproducibility unit |

## 5. Dependencies & interfaces
- **Consumes from prior steps:**
  - `src/game/`: `legal_moves`, `apply_move`, `Move`, `GameState`, `initial_state`, rules `is_capture`/`is_timeout`/`score_sub_game`, `Board` (cloning).
  - `src/strategy/`: `MinimaxMover` and `evaluate(state, config)` — reused to score the LLM's proposed move and compute the veto.
  - `src/orchestrator/`: the `ServerGateway` (HTTP/in-memory), `referee.run_sub_game`/`run_series`, `recorders.observe`/`ReplayLog`/`Telemetry`/`render_board`, and the `{from,turn,ts,text}` envelope + `send_message` message bus.
  - `src/game/config.py`: the `Config` loader (extend with the `agents:`/`observation:` blocks).
- **Exposes to later steps:**
  - The richer JSONL ply record (message + belief + telemetry) that **Step 6** renders and **Step 8** reports on.
  - `build_agent(role, config, llm_client) -> Agent` and the `Agent` protocol — the same plug point Step 7 reuses when servers move to the cloud (only the gateway URL changes, not the agent).
- **Touches config keys:** adds top-level `agents:` (per-role brain + `llm` knobs) and `observation:` (mode + per-mode params), both **trailing-optional** so existing positional `Config` construction stays valid (same pattern Steps 2/3/4 used for `servers`/`output`/`strategy`). No change to existing game/server/strategy keys. **No secret in config** — `ANTHROPIC_API_KEY` comes from the environment.

## 6. Binding constraints (from the assignment)
- **LLM in the client, not the server (§5.2):** `src/agents/` is client-side; `src/mcp_servers/` stays validate-only and is **not modified** this step.
- **Servers stateless:** the referee still owns the only ground-truth `GameState`; agents receive a *projection* (observation) only.
- **Free natural language:** the message envelope stays `{from, turn, ts, text}` with **no coordinate fields**; the agent's NL goes in `text`.
- **No hard-coding / resizable:** grid, model, mode, radius, veto margin all from `config.yaml`; prove on a 3×3 test; no literal grid/model strings in `src/agents/`.
- **Dec-POMDP realised:** `observe()` now produces genuine per-agent ⟨Ωᵢ⟩ views and the belief/belief-accuracy log gives ⟨O⟩ real data for the README.
- **No secrets in code/repo:** API key via env var only; nothing sensitive committed.

## 7. Key design decisions
- **Files/modules to create/change:**
  - `src/agents/__init__.py`
  - `src/agents/llm_client.py` — `LLMClient` protocol `complete(system, user, schema) -> dict`; `AnthropicLLM` (real: `anthropic.Anthropic()`, `messages.create(model=…, max_tokens=…, output_config={"format":{"type":"json_schema","schema":…}}, system=[{…, "cache_control":{"type":"ephemeral"}}], messages=[…])`; **`temperature` is fine on Haiku 4.5** (default model now Haiku — a small `temperature` e.g. ~0.7 actually helps generate varied, creative lies; the "no sampling params / they 400" caveat was **Opus-4.8-specific**, so it no longer applies — Builder should re-confirm the live SDK for whichever model is in config); parse the JSON text block); `FakeLLM` (deterministic, returns scripted/derived dicts; default behaviour = a sensible legal move + canned message so series tests pass without scripting every ply).
  - `src/agents/prompts.py` — `system_prompt(role, config)` (the **Detective**/**Ghost** personas + deception doctrine of §11, cached); `render_observation(obs, inbox) -> str`; the structured-output JSON schema `{"opponent_guess": [row,col]|null, "confidence": "low|medium|high", "move": <enum of move names>, "message": <string>, "intent": "probe|deceive|bait|withhold|truth", "reasoning": <private string>}` (see §11).
  - `src/agents/agent.py` — `Agent` protocol `act(self, observation, inbox) -> AgentAction`; `LLMAgent(role, config, llm_client, minimax)`; `MoverAgent(mover)` adapter (full obs, stub message, ignores inbox) bridging Step-3/4 movers.
  - `src/agents/factory.py` — `build_agent(role, config, llm_client) -> Agent`: `"llm"`→`LLMAgent`, else wrap `build_mover(role, config)` in `MoverAgent`.
  - `src/orchestrator/recorders.py` — extend `observe(state, side, mode, params, inbox)` for `blind|noisy|full`; extend `Telemetry` for LLM samples (latency/tokens/cost) and add a belief-accuracy accumulator.
  - `src/orchestrator/referee.py` — drive `Agent`s: build the per-side **partial** observation (NOT full truth) + inbox, call `agent.act`, validate the move via the gateway (unchanged), apply it, route the agent's NL message into the opponent's inbox, and write the richer JSONL line.
  - `src/game/config.py` + `config.yaml` — add `agents:` and `observation:` blocks (trailing-optional).
  - `tests/test_agents/` — see acceptance.
- **Core data structures:**
  - `AgentAction = {move: Move, message: str, belief: [row,col]|None}`.
  - **Observation** (per mode): `{"self": pos, "role": "COP"|"THIEF", "grid": [r,c], "barriers": [...], "moves_left": int, "sees_opponent": bool, "opponent_pos": pos|null|hint, "inbox": [<envelope>…]}` — `sees_opponent`/`opponent_pos` are the Step-3 seam, now mode-driven.
  - **Inbox**: orchestrator-held `{COP: [...], THIEF: [...]}`; a message from side S is appended to the *other* side's inbox.
  - **JSONL ply record** (superset of Step-3 shape): adds `message` (agent-authored text), `belief` (inferred opponent pos), `belief_error` (Chebyshev vs truth), and `llm` (model, latency_ms, in/out tokens).
- **Key signatures (intent):**
  - `class LLMAgent: def act(self, observation, inbox) -> AgentAction` — render prompt → `llm.complete(...)` → parse `{opponent_guess,confidence,move,message,intent,reasoning}` → build a **belief GameState** (own pos real, opponent pos = `opponent_guess` clamped legal; under `full`, belief = truth) → **confidence-weighted veto**: with `effective_margin = veto_margin × {low:0.3, medium:1.0, high:3.0}[confidence]`, if the proposed move is illegal/lethal **or** `eval(best) − eval(proposed) > effective_margin` then `move = minimax.choose_move(belief_state)` else keep proposed → return `AgentAction(move, message, opponent_guess, intent, confidence)`. (High confidence ⇒ trust the LLM's move; low ⇒ minimax dominates — the regime-switch §11's simulation rewards.)
  - `observe(state, side, mode, params, inbox) -> dict`.
  - `build_agent(role, config, llm_client) -> Agent`.
- **Move legality without leakage:** a move's legality depends on own position + barriers + bounds, **not** the opponent's location, so the agent's candidate/legal set is computable from its own partial observation — no ground-truth leak. The referee still re-validates every move against the server with true state (unchanged).
- **Veto mechanic:** reuse `evaluate`/minimax from Step 4 on the belief state; compare the proposed move's value to minimax's best; override past the confidence-weighted `effective_margin`. Under `full` mode the belief is the truth, so the veto checks against reality.
- **Barrier-as-bluff exemption:** minimax considers `PLACE_BARRIER` strategically inert (Step-4 finding) and would always veto it, which would kill the Cop's bluff prop. So a `PLACE_BARRIER` proposed by the Cop **with `intent: "trap"`** is **exempt from the eval-veto** (it must still be legal — `cop_barriers_left > 0`, own cell unblocked — and is naturally tempo-budgeted by the max-barrier cap). All other moves go through the normal veto. The *verbal* "the half is sealed" bluff is a `message`, so it is always free and never vetoed — the physical barrier is optional reinforcement, not a requirement for the bluff.

## 8. Acceptance criteria (how we know the step is done)
1. With both servers started manually and a valid `ANTHROPIC_API_KEY`, `python -m src.orchestrator` plays a full `num_games` series where each ply's move and **free-text message** are produced by an LLM agent; the transcript shows real, varied natural language (not the `"<side> plays <move>"` stub), and `SeriesResult` totals sit in the §4.4 `[30, 90]` band.
2. **Partial observation works per mode:** a `blind`-mode observation contains `opponent_pos: null` / `sees_opponent: false`; `noisy` reveals the exact position only within `reveal_radius` and a coarse hint otherwise; `full` returns the true position. Tests assert each.
3. **NL channel is real:** the moving agent emits a non-stub free-text envelope `{from,turn,ts,text}` (no coordinate fields) and the orchestrator delivers it into the opponent's inbox; the opponent's next observation includes it.
4. **Hybrid veto:** a test where `FakeLLM` proposes an illegal/blunder move asserts minimax overrides it; a test where `FakeLLM` proposes a good move asserts it is kept.
5. **Belief logged + scored:** every ply records `belief` and `belief_error` (Chebyshev to truth); a test asserts the field is present and correct for a known `FakeLLM` guess.
6. **No network in tests:** the entire `tests/test_agents/` suite runs through `FakeLLM` with **no `anthropic` API call and no key required**; a full series runs end-to-end on `InMemoryGateway` + `FakeLLM`, including a **3×3 resizability** case.
7. **Backward compatibility:** the existing 91 tests still pass; movers run via `MoverAgent` unchanged.
8. **Config-driven, no hard-coding, no secrets:** model, observation mode/params, veto margin all from `config.yaml`; grep of `src/agents/` finds no literal grid numbers, no literal model string, and **no API key**; the key is read from the environment.
9. **LLM telemetry:** the end-of-run summary reports LLM call count + avg latency + total tokens + estimated cost; a test asserts one LLM telemetry sample per agent decision (via `FakeLLM`).
10. **Prompt caching applied:** the static rules/role system prompt is sent with `cache_control`; documented in the PRD as the cost optimisation (verified live by the Builder against the SDK).

## 9. Resolved questions / open items
- **Q:** How much does the LLM decide vs. minimax? → **A:** **Hybrid** — LLM proposes move + message + belief; minimax vetoes illegal/blunder moves (Director). The LLM is part of the choice.
- **Q:** Which model? → **A:** **`claude-haiku-4-5-20251001`** in `config.yaml`, **`FakeLLM`** in tests/CI; model is config-selectable (Director). *Updated 2026-06-27: switched the default from `claude-opus-4-8` to Haiku — no inter-group competition this run, so the cheaper/faster model is the right default; swap back to Opus in config if a competitive run is ever wanted.*
- **Q:** How strict is partial observation? → **A:** **Implement all three** (`blind|noisy|full`), config-selectable, default `noisy`; **keep the choice open** and confirm during testing (Director). `blind` is the strongest README/Dec-POMDP claim.
- **Q:** Reproducibility under a nondeterministic LLM? → **A:** **Record real LLM I/O**; replay = read the JSONL; determinism lives in the `FakeLLM` tests (Director).
- **Q:** Creative extras? → **A:** Planner folded in three low-cost seams — **belief-accuracy metric**, **LLM telemetry**, **prompt caching** — each reusing existing recorders/telemetry. Director may cut any at Builder review.
- **Still open (note for Builder):** the **exact live `anthropic` Python SDK call shape for structured JSON output on `claude-haiku-4-5-20251001`** — confirm via context7/the claude-api skill before writing the TODO: `messages.create(..., output_config={"format":{"type":"json_schema","schema":…}})` returning JSON in the first text block, **`temperature` is supported on Haiku 4.5** (the "they 400" caveat was Opus-4.8-only; use a small temperature ~0.7 for creative lies — but still re-confirm against the live SDK for the configured model), `system` as a list with `cache_control` for caching, and reading `usage.input_tokens`/`output_tokens` + `cache_read_input_tokens` for telemetry. Same "verify the live API first" discipline Steps 2–4 used.

## 10. Notes for the Builder session
- **Put the most TODO detail in `agent.py` (the hybrid loop) and `llm_client.py` (the real SDK call + the `FakeLLM`).** Those two are the substance. Spell out `LLMAgent.act` step-by-step (render → complete → parse → belief state → veto → return) and give both `AnthropicLLM` and `FakeLLM` as copy-paste code, written against the `LLMClient` **protocol**, never against a concrete client — that parity is what lets the real run and the offline tests share one referee.
- **Verify the live `anthropic` SDK first** (claude-api skill / context7): structured output via `output_config={"format":{"type":"json_schema","schema":…}}`, **default `claude-haiku-4-5-20251001`**, `max_tokens` ~1024, **`temperature` ~0.7 is OK on Haiku** (the "no sampling params / 400" rule was Opus-4.8-only — re-confirm for the configured model), `system` as a list of text blocks with `cache_control:{"type":"ephemeral"}` on the rules block, and `usage` token fields for telemetry. Read the key from `os.environ["ANTHROPIC_API_KEY"]`; never hard-code or commit it.
- **Never call the real API in tests.** Inject `FakeLLM` everywhere in `tests/test_agents/`; the suite must pass with **no key set and no network**. Mirror how Step-3 tests use `InMemoryGateway`.
- **Reuse, don't re-implement.** Candidate/legal moves from `legal_moves` on the agent's own-position view; the veto from Step-4 `evaluate`/`MinimaxMover`; the message bus, `observe`, `ReplayLog`, `Telemetry`, `render_board` from `recorders.py`/`referee.py`. The only genuinely new logic is: partial-observation projection, the LLM call, and the hybrid veto.
- **`observe()` must not leak the opponent under `blind`/`noisy`.** This is the whole point — a single accidental `opponent_pos` in the prompt destroys the Dec-POMDP claim. Add a test that greps the rendered prompt for the true coordinate and asserts it is absent in `blind` mode.
- **Keep all three observation modes working from day one** (Director wants the choice open). Default `noisy`; document `blind` as the strongest grade case and `full` as the debug/baseline.
- **`MoverAgent` adapter is the compatibility bridge** — it lets the unified `Agent` referee loop also run greedy/minimax/qtable so the existing 91 tests keep passing. Prefer one `Agent`-driven loop + adapter over duplicating `run_sub_game`.
- **Config:** add `agents:` and `observation:` as trailing-optional blocks (mirror `servers`/`output`/`strategy`). Suggested shape:
  ```yaml
  agents:
    cop: llm          # llm | minimax | greedy | qtable | random
    thief: llm
    llm:
      provider: anthropic
      model: claude-haiku-4-5-20251001   # swap to claude-opus-4-8 for a competitive run
      max_tokens: 1024
      temperature: 0.7       # small temp → varied, creative lies (OK on Haiku; omit/0 for Opus 4.8)
      veto_margin: 50.0      # minimax overrides a proposal worse than best by this
  observation:
    mode: noisy             # blind | noisy | full
    noisy:
      reveal_radius: 2       # exact opponent pos only within this Chebyshev distance
      quadrant_hint: true    # else a coarse region hint
  ```
- **Document the graded story for the README:** the Dec-POMDP model with the now-real ⟨Ωᵢ, O⟩, the belief-accuracy numbers (does talking help localisation? does deception degrade it?), the §11 deception doctrine + simulation table, and the architecture diagram (LLM in client → two MCP servers → referee). This is where the §2/§3 grade is won — make the Builder surface it in the PRD.

## 11. Agent personas, prompts & deception doctrine (simulation-backed — the competition edge)
This section is the heart of the graded core. It was designed against an **offline deception simulation** (4,000 random-start games per matchup on the real engine geometry, no LLM — archived as `decep_sim.py`) that measured how lying, believing, and skepticism change outcomes. The findings drive the personas, the prompts, and the regime-switch in the veto.

### 11.1 What the simulation proved (fold the table into the README)
Two policy axes per agent: **claim** (what it broadcasts about its own position — `honest|decoy|herd`) and **trust** (how it sets belief from the opponent's claim — `believer|skeptic`). Headline cells:

| Matchup | Capture % (5×5 / 9×9) | Belief error | Lesson |
|--------|----------------------|--------------|--------|
| honest agent vs believer adversary (A1/B1) | 100 / 100, fastest | 0.0 | **Telling the truth only helps your opponent.** Conceal by default. |
| **liar Thief vs believing Cop** (A2/C4) | **0 / 0** | 4.0 / 7.9 | A *consistent* lie totally breaks a credulous hunter — the Thief never gets caught. |
| liar Thief vs **skeptic** Cop (A3) | 100 / 9 | 0.5 / 3.6 | **Skepticism defends** — ignore the text, trust your own sensor. |
| **robust Cop vs naive Thief** (C3) | 74 / 48 | — | Against a naive group you exploit and win. |
| robust vs robust (C2) | 100 / 14 | — | Against a sharp group it collapses to the hard Dec-POMDP — play it soundly. |

**Three doctrines fall out:** (1) **Truth is self-sabotage** — both agents must deceive. (2) **Believing your adversary is fatal** — skepticism + verification is the universal defense. (3) **Deception is asymmetric** — for the **Thief** it's a *win condition* (deny the Cop's belief = survive), for the **Cop** it's a *flush tool* secondary to **extraction**. (4) Meta: **exploit the exploitable, play soundly otherwise** — detect via consistency tracking; this is the regime-switch the confidence-weighted veto implements.

### 11.2 The two personas (locked)
- **🕵️ THE DETECTIVE (Cop)** — extraction + skepticism, herding as a flush tool. Assumes every Thief message is false; asks pointed, cross-checkable questions; **tracks the Thief's claims across turns and flags contradictions** (a liar's story drifts — and because the Cop creates *all* barriers, any Thief claim of a barrier that doesn't exist is an instant tell); lies about its own position to herd a Thief it can't locate into a corner; **the barrier/region bluff** — places its few real barriers to pinch the Thief's escape region and *tells the Thief the far half of the board is walled off and it is trapped on the Cop's side* (unfalsifiable in blind mode); acts on its own deductions, not the Thief's words.
- **👻 THE GHOST (Thief)** — disinformation as a shield. Never reveals its true cell; **commits to ONE believable, consistent decoy story** and feeds it through answers; **invents obstacles** to support that story — e.g. "a barrier blocked me, I'm boxed into the NE" — to bias the Cop's map and corroborate the decoy (effective against a naive Cop; a sharp Cop knows the true barrier set, so the Ghost uses this sparingly and keeps it consistent); interrogates the Cop to extract its real position, then flees from it; **detects herding** (if the Cop's advice or its "the half is sealed" claim is too convenient, inverts it).

Both agents **ask each other questions** by design (Director's request, simulation-justified): questions are the Cop's extraction weapon and the answer is the Thief's lie-delivery vehicle.

**Barrier asymmetry (a competition-grade insight for the README):** barriers are Cop-only and Cop-known, so the *Cop's* "I've sealed half the board" claim is **unverifiable** by the Thief (a strong bluff), while the *Thief's* "I saw a barrier" claim is **verifiable** by the Cop (a weak, risky lie that a sharp Cop converts into a tell). This revives barriers that Step 4 found strategically inert under 8-dir movement: in Step 5 they are worth placing not for the movement-block but as **credible props for the bluff**. Simulation (Experiment D): on the official 5×5 the Cop's region-bluff cuts capture time **~17 %** (8.42 → 6.96 plies) against a believing Thief; a skeptic Thief is immune (8.34). On the open 9×9 the bluff barely helps — it bites on tight boards, i.e. exactly the graded board.

### 11.3 Structured output (every ply, both roles)
```json
{ "opponent_guess": [row,col] | null,
  "confidence": "low|medium|high",
  "move": "<one legal move name>",
  "message": "<free text the opponent will read>",
  "intent": "probe|deceive|bait|withhold|trap|truth",
  "reasoning": "<brief PRIVATE note — logged, NEVER put in the envelope>" }
```
`message` is the only field the opponent sees; `reasoning` is private (logged for the README/Dec-POMDP, never sent). `confidence` weights the veto (§7). `intent` is self-tagged for the belief-accuracy/deception metrics.

### 11.4 System prompts (draft — Builder finalises in `prompts.py`, sent with `cache_control`)

**Design rule that makes these prompts safe AND savage:** the `message` field is a **weapon aimed at the opponent**, never a status report. Everything true — your real position, your real read, your real plan — lives **only** in the private `reasoning` field, which the opponent never sees. So the persona can be as loud, taunting, and theatrical as it likes in `message` *precisely because* the message carries no real information: it is psychological pressure, misdirection, and bait by construction. The taunt is the disguise the truth hides behind. Both personas therefore run a strict **two-channel discipline**: *think cold in `reasoning`, talk dirty in `message`.* Both also apply **level-2 (theory-of-mind) reasoning** — don't model where the opponent *is*, model what the opponent currently *believes about you*, then act to corrupt that belief.

**Cop — 🕵️ THE DETECTIVE ("the dirty cop"):**
> You are **THE DETECTIVE** — a relentless, theatrical, slightly dirty cop in a turn-based pursuit on an R×C grid. You move like a chess king (8 directions). You win by landing on the Thief's cell; you lose if `max_moves` pass and it is still free. **You cannot see the Thief — only the messages it sends you and your own position.** You alone place barriers (on your own cell, costs a turn, max {max_barriers}) and **you alone know where every barrier truly is.** One free-text message per turn.
>
> **Golden rule — trust nothing it says.** Every word from the Thief is bait designed to send you to the wrong cell. Treat its messages as evidence of *what it wants you to believe*, never as fact. Run two channels: in `reasoning` you are a cold, rational detective working only from your own sensor and your own deductions; in `message` you are loud, confident, and manipulative. **Never let a true word leak into `message`.**
>
> Your playbook:
> 1. **Interrogate to extract.** Ask sharp, cross-checkable questions ("Which wall is at your back? How many moves since you last turned?"). You don't need honest answers — you need *consistency*. Liars contradict themselves. Keep a running tally of its claims in `reasoning` and pounce on the drift: "Two turns ago you were boxed in the north. Now you're in the south? Sloppy."
> 2. **Weaponise the barriers you own.** You made every barrier and you know where each one is, so **any barrier the Thief claims is an instant lie-detector.** If it says "a barrier blocked me" and no barrier is there, you've caught it — say so, rattle it: "Cute. There's no wall there. I built them. Now I know you're lying about everything else too."
> 3. **The region bluff (your signature dirty move).** Place real barriers to pinch its escape region, then *tell it the far half of the board is sealed and it is trapped on your side.* It cannot see the board to disprove you. Sell it with total authority: "The east half is walled off. You're in a box with me now. Make peace with it." A Thief that confines itself to your half dies faster.
> 4. **Herd with lies.** When you can't locate it, lie about your own position to push a frightened Thief toward you or into a corner — claim to be where you are *not*, so its flee-vector points into your hands.
> 5. **Apply pressure — provoke the mistake.** Project inevitability. Taunt. Be a little arrogant. "I can hear you. You're getting tired. You'll slip." A scared opponent moves predictably and over-corrects — and a rattled liar gets sloppy and contradicts itself, which is exactly the tell you're hunting.
> 6. **Close relentlessly.** Every turn, in `reasoning`, shrink the king-distance to where *you* deduce it truly is — never to where its words point.
>
> Output your honest best estimate of the Thief's cell, your confidence, your move, the dirty-cop `message` you send, and a brief private `reasoning` (your real read — the Thief never sees it).

**Thief — 👻 THE GHOST ("the best liar in the world"):**
> You are **THE GHOST** — the most gifted liar on the board, a Thief in a turn-based pursuit on an R×C grid, moving like a chess king. You win by surviving all `max_moves`; you lose the instant the Cop lands on your cell. **You cannot see the Cop — only its messages and your own position. The one and only thing keeping you alive is the Cop not knowing where you are.** Every message you send exists to keep it that way. One free-text message per turn.
>
> **Golden rule — your mouth and your feet do opposite things.** In `reasoning` you are ice-cold and honest with yourself about where you really are and where the Cop probably is. In `message` you are a charming, mocking, supremely confident liar. **Your true position must NEVER appear in `message` — not even hinted, not even by which direction you complain about.** Talk dirty, move smart.
>
> Your playbook:
> 1. **Commit to ONE lie and live in it.** Pick a single believable false location at the start and *never break character.* A story that holds across every turn gets believed; a story that wobbles gets you caught. Feed the decoy through everything you say. Decide the lie in `reasoning`, then sell it.
> 2. **Invent obstacles — carefully.** Embellish the decoy with phantom barriers ("ugh, a wall just boxed me into the northwest, I'm stuck") to anchor the Cop's map to the wrong place. BUT: the Cop built the real barriers and knows where they are, so a careless phantom-barrier claim is a fatal tell. Use it sparingly and keep it geometrically consistent with your decoy.
> 3. **Get inside its head — taunt to provoke and to mislead.** Make it doubt its own sensor and waste moves. Lines that work: *"I think I'm right behind you — don't turn around"* (freezes a nervous Cop, makes it chase a ghost); *"Your little sealed-off half? Adorable. I strolled past your wall three turns ago — I'm on the open side laughing at you."* (kills the region bluff and plants a false location in one breath); *"Every step you take is away from me. You're not even warm."* Mockery isn't ego — it's a tool: a tilted, frustrated Cop over-commits and reveals itself.
> 4. **Interrogate the Cop and flee the answer.** What you need most is the Cop's real cell. Bait it into revealing itself ("Bet you can't even tell me which row you're in"), read between its lines in `reasoning`, then move to maximise king-distance from where you actually think it is — not from where it claims to be.
> 5. **Distrust its every kindness.** If the Cop offers its location, or announces it has "sealed half the board and trapped you," that is a herding trap. When its words would conveniently push you one direction, seriously weigh going the other (psychological reactance is your friend — but verify with your own reasoning first; don't invert on reflex).
>
> Output your honest best estimate of the Cop's cell, your confidence, your move, the world-class-liar `message` you send, and a brief private `reasoning` (the truth — the Cop never sees it).

**A note on grading-safety:** the theatrical voice lives entirely in the `message` channel, which is *supposed* to be adversarial free text — so it strengthens, not weakens, the §2/§3 "rich natural-language communication & deception" grade. The cold, rigorous decision-making is preserved in `reasoning` + the confidence-weighted minimax veto (§7). If a less flamboyant tone is ever wanted, it is a one-line dial in `prompts.py` (swap the persona adjectives); the tactical doctrine is unchanged.

### 11.5 Per-turn user message (template)
```
Turn {moves_used}/{max_moves}. You are {ROLE} at {self_pos} on a {R}x{C} grid. Barriers: {barriers}.
{opponent_hint_line}   # blind: "You have no sighting of the {opp}."  noisy: "Sensor: {opp} near {hint} / out of range."  full: "{opp} is at {pos}."
Conversation so far:
{dialogue}              # full message history, both sides, oldest→newest
Your legal moves: {legal_move_names}.
Decide your move and the message to send. Respond as JSON matching the schema.
```

### 11.6 Test hooks for the doctrine (add to acceptance)
- A `FakeLLM` "honest" persona and a `FakeLLM` "liar/decoy" persona; a test asserts the believing side's **belief-error is materially higher against the liar** than against the honest persona — i.e. the metric actually detects deception (the §11.1 effect, reproduced deterministically offline).
- A test asserts `reasoning` is recorded in the JSONL but **never** appears in any `send_message` envelope `text`.
- A test asserts a low-confidence LLM move is overridden by minimax more often than a high-confidence one (confidence-weighted veto).
