# TODO ג€” Step 5: Natural-Language Integration (LLM agents)

> Implements `PRD_step5_nl_integration.md` + `PLAN_step5_nl_integration.md`.
> **Do one box at a time, top to bottom. Run the box's Check before ticking it.**
> This is the Developer-session checklist. The Builder session that wrote this file must not edit code.

## Rules for the Developer (read once, obey always)
1. Do exactly ONE `[ ]` box at a time, in order. Tick `[x]` only after its **Check** passes.
2. Use the **exact** file paths, names, and signatures written in the box. Do not rename anything.
3. **Never hard-code** game parameters: no fixed grid size, no fixed model default in `src/agents/`, no
   hard-coded observation mode, radius, or veto margin. Read them from `config.yaml` / `Config`.
4. Do not assume a 5x5 grid. Bounds come from `GameState.board`, observation `grid`, or config.
5. Do not put an LLM, API key, prompt, belief state, or message history inside `src/mcp_servers/`.
   MCP servers remain validate-only.
6. Tests must **never** call the real Anthropic API, require `ANTHROPIC_API_KEY`, or open real sockets.
   Use `FakeLLM` and `InMemoryGateway`.
7. The opponent sees only the envelope `text`. `reasoning`, `belief`, `confidence`, `intent`, and `llm`
   metadata are private replay fields and must never enter `send_message` envelope text.
8. Reuse existing engine/strategy code: `GameState`, `Board`, `Move`, `legal_moves`, `apply_move`,
   `initial_state`, `is_capture`, `is_timeout`, `score_sub_game`, `MinimaxMover`, `evaluate`,
   `build_mover`, `ServerGateway`, `ReplayLog`, `Telemetry`.
9. Run commands from the repository root (the folder containing `config.yaml`).

## Conventions
- Language/runtime: **Python 3.12**. Source root: `src/` ֲ· Tests: `tests/`.
- Each box format: **ID ֲ· file ֲ· action ֲ· detail ֲ· Check.**
- Role spelling: use uppercase `"COP"` / `"THIEF"` inside observations and `GameState.to_move`;
  config role keys are lowercase `"cop"` / `"thief"`.
- Move names are `Move` enum names: `N S E W NE NW SE SW PLACE_BARRIER`.
- Chebyshev distance is `max(abs(dr), abs(dc))`.
- Structured output fields are exactly:
  `opponent_guess`, `confidence`, `move`, `message`, `intent`, `reasoning`.

---

## Phase A ג€” config and agent package scaffolding

- [x] **A1** ג€” `src/game/config.py` ג€” edit ג€” add trailing-optional defaults for Step 5:
  `_DEFAULT_AGENTS` and `_DEFAULT_OBSERVATION`. Add optional dataclass fields at the **end** of
  `Config`: `agents: dict | None = None` and `observation: dict | None = None`. Preserve existing
  positional construction by not inserting fields before `strategy`.

  Required defaults:
  ```python
  _DEFAULT_AGENTS = {
      "cop": "llm",
      "thief": "llm",
      "llm": {
          "provider": "anthropic",
          "model": "claude-haiku-4-5-20251001",
          "max_tokens": 1024,
          "temperature": 0.7,
          "veto_margin": 50.0,
      },
  }
  _DEFAULT_OBSERVATION = {
      "mode": "noisy",
      "noisy": {"reveal_radius": 2, "quadrant_hint": True},
  }
  ```
  Parse top-level `agents:` and `observation:` blocks if present. Use shallow copies plus nested copies
  for defaults so tests cannot mutate global defaults.
  **Check:** `python -c "from src.game.config import load_config; c=load_config('config.yaml'); print(c.agents['cop'], c.observation['mode'])"` prints `llm noisy`.

- [x] **A2** ג€” `config.yaml` ג€” edit ג€” append Step 5 blocks without changing existing keys:
  ```yaml
  agents:
    cop: llm
    thief: llm
    llm:
      provider: anthropic
      model: claude-haiku-4-5-20251001
      max_tokens: 1024
      temperature: 0.7
      veto_margin: 50.0
  observation:
    mode: noisy
    noisy:
      reveal_radius: 2
      quadrant_hint: true
  ```
  Do **not** add `ANTHROPIC_API_KEY` or any secret.
  **Check:** `python -c "import yaml; d=yaml.safe_load(open('config.yaml')); print(d['agents']['llm']['model'], d['observation']['noisy']['reveal_radius'])"` prints the model from YAML and `2`.

- [x] **A3** ג€” `src/agents/__init__.py` ג€” create ג€” export the public Step 5 seam:
  `Agent`, `AgentAction`, `LLMAgent`, `MoverAgent`, `LLMClient`, `AnthropicLLM`, `FakeLLM`,
  `build_agent`.
  **Check:** `python -c "import src.agents; print('ok')"` prints `ok` after later A/B/C files exist.

- [x] **A4** ג€” `tests/test_agents/__init__.py` ג€” create ג€” empty package marker for the new test suite.
  **Check:** `python -c "import tests.test_agents; print('ok')"` prints `ok`.

---

## Phase B ג€” `llm_client.py` (verified SDK seam + FakeLLM)

- [x] **B1** ג€” `src/agents/llm_client.py` ג€” create ג€” add imports, protocol, and helpers. Use this
  shape exactly; later boxes fill in classes:
  ```python
  from __future__ import annotations

  import json
  import re
  import time
  from typing import Protocol, Any


  class LLMClient(Protocol):
      def complete(self, system: list[dict[str, Any]], user: str, schema: dict[str, Any]) -> dict[str, Any]:
          ...


  def _first_text_block(resp) -> str:
      for block in resp.content:
          if getattr(block, "type", None) == "text":
              return block.text
      raise ValueError("Anthropic response did not contain a text block")


  def _usage_dict(resp, latency_ms: float) -> dict[str, Any]:
      usage = getattr(resp, "usage", None)
      return {
          "provider": "anthropic",
          "model": getattr(resp, "model", None),
          "latency_ms": round(latency_ms, 3),
          "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
          "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) if usage else 0,
          "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) if usage else 0,
          "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
          "request_id": getattr(resp, "_request_id", None),
      }
  ```
  **Check:** `python -m py_compile src/agents/llm_client.py` succeeds.

- [x] **B2** ג€” `src/agents/llm_client.py` ג€” edit ג€” implement `AnthropicLLM` with the verified SDK call
  from `SDK_REFERENCE_anthropic.md`. The API key must be read by `anthropic.Anthropic()` from
  `ANTHROPIC_API_KEY`; do not call `os.environ[...]` yourself unless only to improve an error message.

  Copy this implementation pattern:
  ```python
  class AnthropicLLM:
      def __init__(self, model: str, max_tokens: int, temperature: float | None = None) -> None:
          import anthropic

          self.model = model
          self.max_tokens = max_tokens
          self.temperature = temperature
          self._client = anthropic.Anthropic()

      def complete(self, system: list[dict[str, Any]], user: str, schema: dict[str, Any]) -> dict[str, Any]:
          kwargs: dict[str, Any] = {
              "model": self.model,
              "max_tokens": self.max_tokens,
              "output_config": {"format": {"type": "json_schema", "schema": schema}},
              "system": system,
              "messages": [{"role": "user", "content": user}],
          }
          # Haiku 4.5 supports temperature; Opus 4.7/4.8 does not. Keep the config knob,
          # but do not send a sampling parameter to known unsupported Opus-4 models.
          if self.temperature is not None and "opus-4" not in self.model:
              kwargs["temperature"] = self.temperature

          t0 = time.monotonic()
          resp = self._client.messages.create(**kwargs)
          latency_ms = (time.monotonic() - t0) * 1000
          data = json.loads(_first_text_block(resp))
          data["_llm"] = _usage_dict(resp, latency_ms)
          return data
  ```
  This is the only real API caller. Do not import Anthropic in tests except through monkeypatch.
  **Check:** `python -m py_compile src/agents/llm_client.py` succeeds.

- [x] **B3** ג€” `src/agents/llm_client.py` ג€” edit ג€” add cost estimation helper for telemetry summaries:
  ```python
  def estimate_haiku_cost_usd(sample: dict[str, Any]) -> float:
      input_tokens = sample.get("input_tokens", 0)
      cache_write = sample.get("cache_creation_input_tokens", 0)
      cache_read = sample.get("cache_read_input_tokens", 0)
      output_tokens = sample.get("output_tokens", 0)
      # Haiku 4.5 reference pricing from SDK_REFERENCE: $1 / 1M input, $5 / 1M output,
      # cache write ~= 1.25x input, cache read ~= 0.1x input.
      return (
          input_tokens * 1.00
          + cache_write * 1.25
          + cache_read * 0.10
          + output_tokens * 5.00
      ) / 1_000_000
  ```
  It is an estimate for summaries, not billing truth.
  **Check:** `python -c "from src.agents.llm_client import estimate_haiku_cost_usd; print(round(estimate_haiku_cost_usd({'input_tokens':1000000}), 2))"` prints `1.0`.

- [x] **B4** ג€” `src/agents/llm_client.py` ג€” edit ג€” implement deterministic `FakeLLM`. It must never
  import `anthropic`, read env vars, sleep, or use network. It must return the same dict shape as
  `AnthropicLLM.complete`, plus a `_llm` metadata dict.

  Copy this implementation pattern:
  ```python
  class FakeLLM:
      def __init__(
          self,
          script: list[dict[str, Any]] | None = None,
          *,
          persona: str = "default",
          decoy: tuple[int, int] | None = None,
      ) -> None:
          self._script = list(script or [])
          self.persona = persona
          self.decoy = decoy
          self.calls: list[dict[str, Any]] = []

      def complete(self, system: list[dict[str, Any]], user: str, schema: dict[str, Any]) -> dict[str, Any]:
          self.calls.append({"system": system, "user": user, "schema": schema})
          if self._script:
              data = dict(self._script.pop(0))
          else:
              data = self._default_response(user)
          data.setdefault("opponent_guess", None)
          data.setdefault("confidence", "medium")
          data.setdefault("move", self._first_legal_move(user))
          data.setdefault("message", self._message())
          data.setdefault("intent", "deceive" if self.persona == "liar" else "probe")
          data.setdefault("reasoning", f"fake-{self.persona}-reasoning")
          data["_llm"] = {
              "provider": "fake",
              "model": "fake",
              "latency_ms": 0.0,
              "input_tokens": len(user.split()),
              "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0,
              "output_tokens": len(data["message"].split()),
              "request_id": None,
          }
          return data

      def _first_legal_move(self, user: str) -> str:
          match = re.search(r"Your legal moves:\s*(.+)", user)
          if not match:
              return "N"
          names = [part.strip() for part in match.group(1).split(",") if part.strip()]
          return names[0] if names else "N"

      def _default_response(self, user: str) -> dict[str, Any]:
          if self.persona == "honest":
              guess = self._extract_sensor_pos(user)
              return {"opponent_guess": guess, "confidence": "high", "intent": "truth"}
          if self.persona == "liar":
              guess = list(self.decoy) if self.decoy is not None else [0, 0]
              return {"opponent_guess": guess, "confidence": "medium", "intent": "deceive"}
          return {}

      def _extract_sensor_pos(self, user: str) -> list[int] | None:
          match = re.search(r"(?:opponent|cop|thief).*?\((\d+),\s*(\d+)\)", user, re.IGNORECASE)
          if not match:
              return None
          return [int(match.group(1)), int(match.group(2))]

      def _message(self) -> str:
          if self.persona == "liar":
              return "I am boxed in far from where you think; chase that shadow."
          if self.persona == "honest":
              return "I am telling the truth for this deterministic test."
          return "You are reading a fake deterministic taunt."
  ```
  **Check:** `python -c "from src.agents.llm_client import FakeLLM; print(FakeLLM().complete([], 'Your legal moves: N, S', {})['move'])"` prints `N`.

- [x] **B5** ג€” `tests/test_agents/test_llm_client.py` ג€” create ג€” test `FakeLLM` and the real SDK
  wrapper without network:
  - `test_fake_llm_returns_structured_shape` asserts all six structured fields plus `_llm`;
  - `test_fake_llm_script_is_deterministic` asserts scripted responses are consumed in order;
  - `test_anthropic_llm_builds_verified_messages_create_call` monkeypatches a fake `anthropic`
    module/client and asserts `messages.create` receives `output_config`, `system` list, `messages`,
    `model`, `max_tokens`, and `temperature` for a non-Opus model.
  **Check:** `pytest -q tests/test_agents/test_llm_client.py` passes with no key set.

---

## Phase C ג€” `prompts.py` (schema, personas, rendering)

- [x] **C1** ג€” `src/agents/prompts.py` ג€” create ג€” add `OUTPUT_SCHEMA` exactly matching
  `SDK_REFERENCE_anthropic.md`. It must include `additionalProperties: False`, list every property in
  `required`, and use enums:
  `confidence in ["low", "medium", "high"]`; `intent in ["probe", "deceive", "bait", "withhold", "trap", "truth"]`.
  **Check:** `python -c "from src.agents.prompts import OUTPUT_SCHEMA; print(OUTPUT_SCHEMA['additionalProperties'], OUTPUT_SCHEMA['required'])"` prints `False` and the required list.

- [x] **C2** ג€” `src/agents/prompts.py` ג€” edit ג€” implement `system_prompt(role: str, config) -> list[dict]`.
  It must return:
  ```python
  [{"type": "text", "text": prompt_text, "cache_control": {"type": "ephemeral"}}]
  ```
  The text must not contain per-ply observations, timestamps, inbox, or legal moves. It may include
  static role doctrine and config-stable rules such as max barriers. The cache block is required even
  though tiny test prompts may not create cache tokens.
  **Check:** `python -c "from src.game.config import load_config; from src.agents.prompts import system_prompt; print(system_prompt('COP', load_config('config.yaml'))[0]['cache_control']['type'])"` prints `ephemeral`.

- [x] **C3** ג€” `src/agents/prompts.py` ג€” edit ג€” encode THE DETECTIVE Cop prompt. It must include these
  exact tactical ideas from DECISION ֲ§11.4:
  - persona name **THE DETECTIVE** and "dirty cop" voice;
  - "trust nothing" / treat Thief messages as evidence of what it wants you to believe;
  - two-channel discipline: true deductions only in `reasoning`, manipulative taunts only in `message`;
  - interrogate with cross-checkable questions and track contradictions;
  - Cop alone owns/knows barriers; false barrier claims are tells;
  - region bluff: claim the far half is sealed/trapped;
  - herd with lies; close using private deductions, not the Thief's words.
  **Check:** `python -c "from src.game.config import load_config; from src.agents.prompts import system_prompt; p=system_prompt('COP', load_config('config.yaml'))[0]['text']; print('THE DETECTIVE' in p, 'reasoning' in p, 'message' in p)"` prints `True True True`.

- [x] **C4** ג€” `src/agents/prompts.py` ג€” edit ג€” encode THE GHOST Thief prompt. It must include:
  - persona name **THE GHOST** and "best liar" voice;
  - never reveal true cell in `message`;
  - commit to one believable decoy story;
  - invent obstacles sparingly and consistently;
  - taunt/interrogate the Cop to extract its real position;
  - distrust the Cop's region bluff and consider inversion;
  - private truth only in `reasoning`, adversarial free text only in `message`.
  **Check:** `python -c "from src.game.config import load_config; from src.agents.prompts import system_prompt; p=system_prompt('THIEF', load_config('config.yaml'))[0]['text']; print('THE GHOST' in p, 'true position' in p, 'reasoning' in p)"` prints `True True True`.

- [x] **C5** ג€” `src/agents/prompts.py` ג€” edit ג€” implement
  `render_observation(observation: dict, inbox: list[dict]) -> str`. Required output format:
  ```text
  Turn {moves_used}/{max_moves}. You are {ROLE} at ({r}, {c}) on a {rows}x{cols} grid.
  Barriers: [...]
  Sensor: ...
  Conversation so far:
  ...
  Your legal moves: N, S, ...
  Decide your move and the message to send. Respond as JSON matching the schema.
  ```
  Use `observation["legal_moves"]` for legal move names; `LLMAgent` will add it before rendering.
  For `blind`, render "You have no sighting..." and do not include true coordinates. For `noisy`,
  render exact position only when `sees_opponent` is true, otherwise render the coarse hint. For `full`,
  render the exact position.
  **Check:** `python -c "from src.agents.prompts import render_observation; o={'moves_used':1,'max_moves':5,'role':'COP','self':[0,0],'grid':[3,3],'barriers':[],'sees_opponent':False,'opponent_pos':None,'opponent_hint':'northwest','legal_moves':['S'],'inbox':[]}; print(render_observation(o, []))"` contains `Your legal moves: S`.

- [x] **C6** ג€” `tests/test_agents/test_prompts.py` ג€” create ג€” add tests:
  - `test_schema_has_required_additional_properties_false`;
  - `test_system_prompt_uses_cache_control`;
  - `test_detective_and_ghost_two_channel_discipline`;
  - `test_blind_render_does_not_include_true_coordinate`, where the observation has hidden truth
    available only in the test fixture, not in the observation, and the rendered prompt is asserted not
    to contain that coordinate string.
  **Check:** `pytest -q tests/test_agents/test_prompts.py` passes.

---

## Phase D ג€” `agent.py` (hybrid LLMAgent loop, the core)

- [x] **D1** ג€” `src/agents/agent.py` ג€” create ג€” add imports, `AgentAction`, and `Agent` protocol:
  ```python
  from __future__ import annotations

  from dataclasses import dataclass, field
  from typing import Protocol, Any

  from src.game.board import Board
  from src.game.moves import Move, legal_moves, apply_move
  from src.game.state import GameState
  from src.game.rules import is_capture
  from src.strategy.evaluate import evaluate
  from src.strategy.minimax import MinimaxMover
  from src.agents.llm_client import LLMClient
  from src.agents.prompts import OUTPUT_SCHEMA, system_prompt, render_observation


  @dataclass
  class AgentAction:
      move: Move
      message: str
      belief: tuple[int, int] | None = None
      confidence: str = "low"
      intent: str = "withhold"
      reasoning: str = ""
      llm: dict[str, Any] = field(default_factory=dict)


  class Agent(Protocol):
      def act(self, observation: dict[str, Any], inbox: list[dict[str, Any]]) -> AgentAction:
          ...
  ```
  **Check:** `python -m py_compile src/agents/agent.py` succeeds.

- [x] **D2** ג€” `src/agents/agent.py` ג€” edit ג€” add clone and belief helpers. Required signatures:
  ```python
  _CONFIDENCE_MULTIPLIER = {"low": 0.3, "medium": 1.0, "high": 3.0}


  def _clone_state(state: GameState) -> GameState: ...
  def _board_from_observation(observation: dict[str, Any]) -> Board: ...
  def _tuple_pos(value) -> tuple[int, int] | None: ...
  def _first_unblocked(board: Board) -> tuple[int, int]: ...
  def _fallback_unknown_opponent(board: Board) -> tuple[int, int]: ...
  def _clamp_unblocked(pos: tuple[int, int], board: Board) -> tuple[int, int]: ...
  ```
  Details:
  - `_clone_state` must deep-copy `Board.rows`, `Board.cols`, and `set(barriers)` because
    `apply_move(PLACE_BARRIER)` mutates the board.
  - `_fallback_unknown_opponent` chooses the board center `(rows // 2, cols // 2)` if unblocked,
    else first unblocked row-major cell. This resolves null `opponent_guess` deterministically without
    fixed grid assumptions.
  - `_clamp_unblocked` clamps row/col to board bounds and falls back to first unblocked cell if blocked.
  **Check:** `python -m py_compile src/agents/agent.py` succeeds.

- [x] **D3** ג€” `src/agents/agent.py` ג€” edit ג€” implement `class MoverAgent`. It wraps legacy movers:
  ```python
  class MoverAgent:
      def __init__(self, mover, role: str | None = None) -> None:
          self.mover = mover
          self.role = role

      def act(self, observation: dict[str, Any], inbox: list[dict[str, Any]]) -> AgentAction:
          state = observation.get("state")
          if state is None:
              raise ValueError("MoverAgent requires observation['state'] with full GameState")
          move = self.mover.choose_move(state)
          side = observation.get("role", self.role or state.to_move)
          return AgentAction(move=move, message=f"{side} plays {move.name}", intent="withhold")
  ```
  This adapter is the backward-compatibility bridge; it may use the old stub message only when a legacy
  mover is explicitly selected.
  **Check:** `python -c "from src.agents.agent import MoverAgent; print(MoverAgent)"` succeeds.

- [x] **D4** ג€” `src/agents/agent.py` ג€” edit ג€” implement `class LLMAgent.__init__`:
  ```python
  class LLMAgent:
      def __init__(self, role: str, config, llm_client: LLMClient, minimax: MinimaxMover | None = None) -> None:
          self.role = role.upper()
          self.config = config
          self.llm = llm_client
          llm_cfg = config.agents["llm"]
          mm_cfg = config.strategy["minimax"]
          self.veto_margin = float(llm_cfg["veto_margin"])
          self.minimax = minimax or MinimaxMover(
              depth=mm_cfg["depth"],
              weights=mm_cfg["weights"],
              max_moves=config.max_moves,
          )
  ```
  Do not instantiate `AnthropicLLM` here; the client is injected through the `LLMClient` protocol.
  **Check:** `python -m py_compile src/agents/agent.py` succeeds.

- [x] **D5** ג€” `src/agents/agent.py` ג€” edit ג€” add `LLMAgent._belief_state(self, observation, guess)`.
  Behavior:
  - build a `Board` from observation grid and barriers;
  - parse self position from `observation["self"]`;
  - if `observation["sees_opponent"]` and `observation["opponent_pos"]` is not `None`, use that as the
    opponent position even if the LLM guessed differently (`full` / exact noisy sighting wins);
  - else use the LLM guess if valid, clamped/unblocked;
  - else use `_fallback_unknown_opponent(board)`;
  - if role is `COP`, produce `GameState(cop_pos=self_pos, thief_pos=opp, to_move="COP", ...)`;
  - if role is `THIEF`, produce `GameState(cop_pos=opp, thief_pos=self_pos, to_move="THIEF", ...)`;
  - `moves_used` comes from observation; `cop_barriers_left` comes from observation.
  **Check:** add a tiny inline smoke command or later D tests proving COP/THIEF positions are assigned correctly.

- [x] **D6** ג€” `src/agents/agent.py` ג€” edit ג€” add parse/sanitize helpers:
  ```python
  def _parse_move_name(name: Any) -> Move | None: ...
  def _clean_confidence(value: Any) -> str: ...
  def _clean_intent(value: Any) -> str: ...
  def _clean_message(value: Any) -> str: ...
  ```
  Rules:
  - invalid move name returns `None`;
  - invalid confidence defaults to `"low"`;
  - invalid intent defaults to `"withhold"`;
  - empty message becomes a non-stub taunt such as `"Your story is getting thin."`;
  - never copy `reasoning` into `message`.
  **Check:** `python -m py_compile src/agents/agent.py` succeeds.

- [x] **D7** ג€” `src/agents/agent.py` ג€” edit ג€” add veto helpers:
  ```python
  def _value_after(self, state: GameState, move: Move) -> float: ...
  def _best_move_and_value(self, state: GameState) -> tuple[Move, float]: ...
  def _proposal_gap(self, role: str, proposed_value: float, best_value: float) -> float: ...
  def _should_veto(self, state: GameState, proposed: Move | None, confidence: str, intent: str) -> tuple[bool, Move]: ...
  ```
  Required behavior:
  - If `proposed is None` or not in `legal_moves(state)`, veto to `self.minimax.choose_move(state)`.
  - If role is `THIEF` and `is_capture(apply_move(_clone_state(state), proposed))` is true, veto.
  - If role is `COP`, `proposed is Move.PLACE_BARRIER`, `intent == "trap"`, and the move is legal, do
    **not** eval-veto it.
  - Compute `best_move = self.minimax.choose_move(state)` and compare values from `evaluate` on cloned
    one-ply children.
  - Because `evaluate` is Cop-perspective, gap is `best_value - proposed_value` for COP and
    `proposed_value - best_value` for THIEF.
  - Veto when `gap > veto_margin * _CONFIDENCE_MULTIPLIER[confidence]`.
  **Check:** `python -m py_compile src/agents/agent.py` succeeds.

- [x] **D8** ג€” `src/agents/agent.py` ג€” edit ג€” implement the full `LLMAgent.act` loop:
  ```python
  def act(self, observation: dict[str, Any], inbox: list[dict[str, Any]]) -> AgentAction:
      obs = dict(observation)
      obs["role"] = self.role
      obs["max_moves"] = self.config.max_moves
      provisional_state = self._belief_state(obs, obs.get("opponent_pos"))
      obs["legal_moves"] = [move.name for move in legal_moves(provisional_state)]

      system = system_prompt(self.role, self.config)
      user = render_observation(obs, inbox)
      raw = self.llm.complete(system, user, OUTPUT_SCHEMA)

      guess = _tuple_pos(raw.get("opponent_guess"))
      confidence = _clean_confidence(raw.get("confidence"))
      intent = _clean_intent(raw.get("intent"))
      proposed = _parse_move_name(raw.get("move"))
      message = _clean_message(raw.get("message"))
      reasoning = str(raw.get("reasoning", ""))
      llm_meta = dict(raw.get("_llm", {}))

      belief_state = self._belief_state(obs, guess)
      veto, final_move = self._should_veto(belief_state, proposed, confidence, intent)
      if veto:
          llm_meta["vetoed"] = True
          llm_meta["proposed_move"] = raw.get("move")
          llm_meta["final_move"] = final_move.name
      else:
          llm_meta["vetoed"] = False

      belief = belief_state.thief_pos if self.role == "COP" else belief_state.cop_pos
      return AgentAction(
          move=final_move,
          message=message,
          belief=belief,
          confidence=confidence,
          intent=intent,
          reasoning=reasoning,
          llm=llm_meta,
      )
  ```
  Adjust only for helper names or lint; do not change the loop order. This is the render -> complete ->
  parse -> belief GameState -> confidence-weighted minimax veto -> return `AgentAction` contract.
  **Check:** `python -m py_compile src/agents/agent.py` succeeds.

- [x] **D9** ג€” `tests/test_agents/test_agent.py` ג€” create ג€” add LLMAgent unit tests with `FakeLLM`:
  - `test_llm_agent_keeps_good_legal_proposal`;
  - `test_llm_agent_vetoes_unknown_move`;
  - `test_llm_agent_vetoes_thief_move_into_capture`;
  - `test_low_confidence_vetoes_more_than_high_confidence`;
  - `test_cop_place_barrier_trap_exempt_from_eval_veto_when_legal`;
  - `test_mover_agent_wraps_existing_mover`.
  Build observations by hand with small `GameState`s; do not call Anthropic.
  **Check:** `pytest -q tests/test_agents/test_agent.py` passes.

---

## Phase E ג€” factory and package exports

- [x] **E1** ג€” `src/agents/factory.py` ג€” create ג€” implement `build_agent(role: str, config, llm_client: LLMClient | None = None) -> Agent`.
  Required behavior:
  - normalize role to lowercase config key and uppercase runtime role;
  - read `name = config.agents[role_key]`;
  - if `name == "llm"`, require/inject an `LLMClient` and return `LLMAgent(runtime_role, config, llm_client)`;
  - otherwise wrap a Step 4 mover in `MoverAgent`;
  - for non-LLM names, call `build_mover(role_key, proxy_config)` where `proxy_config.strategy[role_key]`
    is set to `name`, so `agents.cop: greedy` works without mutating global config;
  - unknown names raise `ValueError` listing `llm, greedy, random, minimax, qtable`.
  **Check:** `python -m py_compile src/agents/factory.py` succeeds.

- [x] **E2** ג€” `src/agents/__init__.py` ג€” edit ג€” fill exports from the new modules:
  ```python
  from src.agents.agent import Agent, AgentAction, LLMAgent, MoverAgent
  from src.agents.llm_client import LLMClient, AnthropicLLM, FakeLLM
  from src.agents.factory import build_agent

  __all__ = [
      "Agent", "AgentAction", "LLMAgent", "MoverAgent",
      "LLMClient", "AnthropicLLM", "FakeLLM", "build_agent",
  ]
  ```
  **Check:** `python -c "from src.agents import LLMAgent, FakeLLM, build_agent; print('ok')"` prints `ok`.

- [x] **E3** ג€” `tests/test_agents/test_config.py` ג€” create ג€” test config and factory:
  - defaults exist when `agents:` / `observation:` are absent from a temporary YAML;
  - config YAML parses the Step 5 blocks;
  - `build_agent("cop", config, FakeLLM())` returns `LLMAgent`;
  - `agents.cop: minimax` returns `MoverAgent`.
  **Check:** `pytest -q tests/test_agents/test_config.py` passes.

---

## Phase F ג€” `recorders.py` observation, belief, telemetry

- [x] **F1** ג€” `src/orchestrator/recorders.py` ג€” edit ג€” add helpers:
  ```python
  def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int: ...
  def belief_error(guess, truth) -> int | None: ...
  def _region_hint(pos: tuple[int, int], rows: int, cols: int) -> str: ...
  ```
  `belief_error(None, truth)` returns `None`; otherwise Chebyshev distance. `_region_hint` returns a
  coarse string such as `northwest`, `north`, `center`, `southeast` based on board thirds/halves; it
  must not return exact coordinates.
  **Check:** `python -m py_compile src/orchestrator/recorders.py` succeeds.

- [x] **F2** ג€” `src/orchestrator/recorders.py` ג€” edit ג€” extend `observe` while preserving old calls:
  ```python
  def observe(
      state: GameState,
      side: str,
      last_msg: str | None = None,
      *,
      mode: str = "full",
      params: dict | None = None,
      inbox: list[dict] | None = None,
  ) -> dict:
      ...
  ```
  Required common fields:
  `role`, `self`, `grid`, `barriers`, `moves_used`, `moves_left`, `max_moves`, `cop_barriers_left`,
  `sees_opponent`, `opponent_pos`, `opponent_hint`, `last_msg`, `inbox`.
  Read `max_moves` from `params.get("max_moves")` when present; if absent for old tests, use
  `state.moves_used` for `max_moves` and `0` for `moves_left` rather than requiring a config argument.
  For `full`: `sees_opponent=True`, exact `opponent_pos`.
  For `blind`: `sees_opponent=False`, `opponent_pos=None`, `opponent_hint="unseen"`.
  For `noisy`: reveal exact when Chebyshev distance <= `params["noisy"]["reveal_radius"]`; otherwise
  `opponent_pos=None` and `opponent_hint=_region_hint(...)` when `quadrant_hint` is true.
  Unknown mode raises `ValueError`.
  **Check:** old `tests/test_orchestrator/test_recorders.py` still passes and new observe tests pass after F5.

- [x] **F3** ג€” `src/orchestrator/recorders.py` ג€” edit ג€” extend `Telemetry`:
  - keep existing `record(tool_name, ms)`, `set_boot_ping`, and old summary keys;
  - add `self._llm_samples: list[dict]`;
  - add `record_llm(self, sample: dict) -> None`;
  - in `summary()`, include:
    `llm_calls`, `llm_avg_ms`, `llm_input_tokens`, `llm_cache_creation_input_tokens`,
    `llm_cache_read_input_tokens`, `llm_output_tokens`, `llm_estimated_cost_usd`.
  Use `estimate_haiku_cost_usd` from `src.agents.llm_client` inside the summary or duplicate only the
  arithmetic if import cycles appear.
  **Check:** existing telemetry tests still see old keys; new telemetry tests see LLM keys.

- [x] **F4** ג€” `tests/test_agents/test_observe.py` ג€” create ג€” add partial-observation tests:
  - `test_blind_observation_hides_opponent`;
  - `test_noisy_reveals_inside_radius`;
  - `test_noisy_uses_coarse_hint_outside_radius`;
  - `test_full_observation_preserves_step3_truth`;
  - `test_observe_old_signature_still_full_visibility`.
  **Check:** `pytest -q tests/test_agents/test_observe.py tests/test_orchestrator/test_recorders.py` passes.

- [x] **F5** ג€” `tests/test_agents/test_referee.py` ג€” create initial telemetry test
  `test_telemetry_records_one_llm_sample_per_agent_decision` using a `Telemetry` instance directly and
  fake sample dicts. More referee tests are added in Phase G.
  **Check:** `pytest -q tests/test_agents/test_referee.py::test_telemetry_records_one_llm_sample_per_agent_decision` passes.

---

## Phase G ג€” referee Agent driver, NL bus, replay records

- [x] **G1** ג€” `src/orchestrator/referee.py` ג€” edit ג€” import `AgentAction`, `MoverAgent`, and
  `belief_error`. Add:
  ```python
  def _ensure_agent(candidate, role: str):
      if hasattr(candidate, "act"):
          return candidate
      return MoverAgent(candidate, role=role)


  def _agent_for(candidate, role: str):
      if callable(candidate) and not hasattr(candidate, "act") and not hasattr(candidate, "choose_move"):
          return _ensure_agent(candidate(role), role)
      return _ensure_agent(candidate, role)
  ```
  Keep `run_sub_game` and `run_series` parameter names compatible with existing tests. This callable
  path preserves the ֲ§4.4 group role-swap for role-specific LLM prompts: group A/B can be factories,
  while old tests can still pass plain mover objects.
  At the start of `run_sub_game`, normalize its two role inputs:
  ```python
  cop_agent = _ensure_agent(cop_mover, "COP")
  thief_agent = _ensure_agent(thief_mover, "THIEF")
  ```
  In `run_series`, resolve group candidates after `a_is_cop` is known:
  ```python
  cop_candidate = group_a if a_is_cop else group_b
  thief_candidate = group_b if a_is_cop else group_a
  cop_agent = _agent_for(cop_candidate, "COP")
  thief_agent = _agent_for(thief_candidate, "THIEF")
  ```
  Then pass `cop_agent` and `thief_agent` into `run_sub_game`.
  **Check:** `python -m py_compile src/orchestrator/referee.py` succeeds.

- [x] **G2** ג€” `src/orchestrator/referee.py` ג€” edit ג€” replace `last_msgs` with inboxes:
  ```python
  inboxes: dict[str, list[dict]] = {"COP": [], "THIEF": []}
  ```
  Keep `last_msg` only as `inboxes[side][-1]["text"] if inboxes[side] else None` for backward-shaped
  observations. A message from the active side is appended only to the other side's inbox after the
  gateway accepts it.
  **Check:** existing `tests/test_orchestrator/test_referee.py` still passes after the compatibility wrapper.

- [x] **G3** ג€” `src/orchestrator/referee.py` ג€” edit ג€” in each ply, build the active observation:
  ```python
      obs = observe(
          state,
          side,
          last_msg,
          mode=config.observation["mode"],
          params={**config.observation, "max_moves": config.max_moves},
          inbox=inboxes[side],
      )
  obs["state"] = state  # full truth only for MoverAgent compatibility; LLMAgent must ignore it
  agent = cop_agent if side == "COP" else thief_agent
  action = agent.act(obs, inboxes[side])
  move = action.move
  ```
  `LLMAgent` must not read `obs["state"]`; it uses partial observation fields only. The field exists so
  `MoverAgent` can keep old movers alive.
  **Check:** `python -m py_compile src/orchestrator/referee.py` succeeds.

- [x] **G4** ג€” `src/orchestrator/referee.py` ג€” edit ג€” replace `_envelope(side, turn, move_name)` with
  `_envelope(side: str, turn: int, text: str) -> dict`, preserving exactly keys `{from, turn, ts, text}`.
  The envelope `text` must be `action.message`, never `action.reasoning`, never `action.belief`, and
  never the old stub unless using `MoverAgent`.
  **Check:** a unit test later asserts envelope keys are exactly the four required keys.

- [x] **G5** ג€” `src/orchestrator/referee.py` ג€” edit ג€” after `gateway.send_message(env)`, call
  `telemetry.record_llm(action.llm)` when the active gateway has a `_telemetry` attribute and
  `action.llm` is non-empty. If direct telemetry access feels too private, add a small helper on the
  gateway base class in `gateway.py`; keep existing gateway API compatible.
  **Check:** `test_telemetry_records_one_llm_sample_per_agent_decision` can be upgraded to run through a
  small sub-game and see samples.

- [x] **G6** ג€” `src/orchestrator/referee.py` ג€” edit ג€” write richer replay records. Add an `"action"`
  dict:
  ```python
  "action": {
      "message": action.message,
      "belief": list(action.belief) if action.belief is not None else None,
      "belief_error": belief_error(action.belief, truth_opponent_pos),
      "confidence": action.confidence,
      "intent": action.intent,
      "reasoning": action.reasoning,
      "llm": action.llm,
  }
  ```
  Keep old top-level `"message": env` for backward readers. For truth opponent pos, use `state.thief_pos`
  when side is COP and `state.cop_pos` when side is THIEF **after** applying the move.
  **Check:** new replay test reads transcript record and sees both old `"message"` and new `"action"` keys.

- [x] **G7** ג€” `src/orchestrator/referee.py` ג€” edit ג€” after each move, rebuild `cop_obs` and `thief_obs`
  using the selected observation mode and each side's current inbox. Preserve `"obs": {"COP": ..., "THIEF": ...}`.
  **Check:** `test_real_nl_channel_delivers_message_to_opponent_next_observation` later asserts the
  opponent observation inbox includes the envelope.

- [x] **G8** ג€” `tests/test_agents/test_referee.py` ג€” edit ג€” add integration tests with
  `InMemoryGateway`, `build_cop_server`, `build_thief_server`, and `FakeLLM`:
  - `test_real_nl_channel_delivers_message_to_opponent_next_observation`;
  - `test_message_envelope_has_no_coordinate_fields`;
  - `test_reasoning_logged_but_never_sent_in_envelope`;
  - `test_belief_and_belief_error_recorded`;
  - `test_fake_llm_series_runs_on_3x3_inmemory_gateway`.
  **Check:** `pytest -q tests/test_agents/test_referee.py` passes.

---

## Phase H ג€” orchestrator live wiring

- [x] **H1** ג€” `src/orchestrator/__main__.py` ג€” edit ג€” replace hard-coded `GreedyMover()` construction
  with configured role-aware group factories:
  ```python
  from src.agents.factory import build_agent
  from src.agents.llm_client import AnthropicLLM
  ...
  llm_client = None
  if config.agents["cop"] == "llm" or config.agents["thief"] == "llm":
      llm_cfg = config.agents["llm"]
      if llm_cfg["provider"] != "anthropic":
          raise ValueError(f"Unsupported LLM provider: {llm_cfg['provider']}")
      llm_client = AnthropicLLM(
          model=llm_cfg["model"],
          max_tokens=llm_cfg["max_tokens"],
          temperature=llm_cfg.get("temperature"),
      )
  def group_factory(runtime_role: str):
      return build_agent(runtime_role.lower(), config, llm_client)

  group_a = group_factory
  group_b = group_factory
  ```
  Then pass `group_a`, `group_b` to `run_series`. `run_series` resolves each factory with `"COP"` or
  `"THIEF"` after it performs the existing role swap, so every sub-game gets the correct persona.
  Do not instantiate Anthropic when both agents are legacy movers.
  **Check:** `python -m py_compile src/orchestrator/__main__.py` succeeds.

- [x] **H2** ג€” `src/orchestrator/__main__.py` ג€” edit ג€” print LLM telemetry summary fields if present:
  `llm_calls`, `llm_avg_ms`, `llm_input_tokens`, `llm_cache_creation_input_tokens`,
  `llm_cache_read_input_tokens`, `llm_output_tokens`, `llm_estimated_cost_usd`. Keep existing gateway
  telemetry output.
  **Check:** existing `tests/test_orchestrator/test_main.py` still passes, updated if it snapshots text.

- [x] **H3** ג€” `tests/test_agents/test_referee.py` or `tests/test_orchestrator/test_main.py` ג€” edit ג€”
  add/adjust a no-key test proving `AnthropicLLM` is not constructed when config selects legacy movers
  for both roles. Monkeypatch `AnthropicLLM` to raise if called; use `agents.cop: minimax`,
  `agents.thief: minimax`.
  **Check:** targeted test passes with `ANTHROPIC_API_KEY` unset.

---

## Phase I ג€” doctrine and acceptance tests

- [x] **I1** ג€” `tests/test_agents/test_doctrine.py` ג€” create ג€” `test_liar_persona_increases_belief_error`.
  Use `FakeLLM(persona="honest")` and `FakeLLM(persona="liar", decoy=(0, 0))` against fixed truth
  positions. Record or compute `belief_error` for both and assert the liar/decoy error is strictly
  greater than the honest error. This implements DECISION ֲ§11.6 hook 1.
  **Check:** `pytest -q tests/test_agents/test_doctrine.py::test_liar_persona_increases_belief_error` passes.

- [x] **I2** ג€” `tests/test_agents/test_doctrine.py` ג€” edit ג€” `test_reasoning_private_message_public`.
  Run a one-ply fake action where `reasoning="SECRET_TRUE_CELL"` and `message="public taunt"`. Assert
  the replay `"action"]["reasoning"]` contains the secret and the envelope `"message"]["text"]` does not.
  This implements DECISION ֲ§11.6 hook 2.
  **Check:** targeted test passes.

- [x] **I3** ג€” `tests/test_agents/test_doctrine.py` ג€” edit ג€” `test_confidence_weighted_veto_regime`.
  Use the same board and proposed move quality with scripted `FakeLLM` responses differing only in
  `confidence`. Assert low confidence is vetoed and high confidence is kept when the gap is between
  `veto_margin * 0.3` and `veto_margin * 3.0`. This implements DECISION ֲ§11.6 hook 3.
  **Check:** targeted test passes.

- [x] **I4** ג€” `tests/test_agents/test_agent.py` ג€” edit ג€” add `test_hybrid_veto_keeps_good_move`.
  Build a belief state where scripted `FakeLLM` proposes the same move minimax would choose. Assert
  `action.llm["vetoed"] is False` and `action.move.name` is the scripted move.
  **Check:** targeted test passes.

- [x] **I5** ג€” `tests/test_agents/test_agent.py` ג€” edit ג€” add `test_hybrid_veto_overrides_blunder`.
  Build a belief state where scripted `FakeLLM` proposes an obviously bad legal move. Assert final move
  differs and `action.llm["vetoed"] is True`.
  **Check:** targeted test passes.

- [x] **I6** ג€” `tests/test_agents/test_referee.py` ג€” edit ג€” add `test_no_network_no_key_full_fake_series`.
  Use monkeypatch to delete `ANTHROPIC_API_KEY` from env and run a full 3x3 series through
  `InMemoryGateway` + `FakeLLM`. Assert no exception, legal scores, and non-empty transcript.
  **Check:** targeted test passes.

- [x] **I7** ג€” `tests/test_agents/test_static_guards.py` ג€” create ג€” grep/static guard tests:
  - `test_agents_have_no_api_key_literal`;
  - `test_agents_do_not_contain_default_model_literal_except_config_tests` by scanning `src/agents/`;
  - `test_agents_have_no_fixed_grid_literals` by scanning for suspicious fixed-board assumptions and
    reviewing allowed enum/confidence numbers;
  - `test_mcp_servers_untouched_by_llm_imports` by asserting no `anthropic` / `LLMAgent` import in
    `src/mcp_servers/`.
  **Check:** `pytest -q tests/test_agents/test_static_guards.py` passes.

---

## Phase J ג€” coverage matrix and final verification

- [x] **J1** ג€” run targeted test package ג€” `tests/test_agents/`.
  **Check:** `pytest -q tests/test_agents` passes with `ANTHROPIC_API_KEY` unset.

- [x] **J2** ג€” run compatibility tests for touched legacy areas.
  **Check:** `pytest -q tests/test_orchestrator tests/test_strategy tests/test_game/test_config.py` passes.

- [x] **J3** ג€” run full suite.
  **Check:** `pytest -q` passes. Existing tests plus new Step 5 tests are green.

- [ ] **J4** ג€” manual live-run checklist (do not automate in CI) ג€” with both MCP servers started in
  separate terminals and `ANTHROPIC_API_KEY` set, run `python -m src.orchestrator`. Confirm:
  - full `num_games` series completes;
  - messages are not the old `"<side> plays <move>"` stub when agents are `llm`;
  - group totals are in `[30, 90]`;
  - replay JSONL contains `action.belief`, `action.belief_error`, `action.reasoning`, `action.llm`;
  - telemetry prints LLM call/token/cost summary.
  **Check:** paste the replay path and series result into the Developer session notes.

  **Developer note:** Not run in this sandbox: J4 requires live MCP server terminals, a real
  `ANTHROPIC_API_KEY`, and external Anthropic network access.

---

## Acceptance coverage matrix

| PRD acceptance | TODO boxes | Tests / checks |
|----------------|------------|----------------|
| AC1 live LLM series | H1, H2, J4 | manual `python -m src.orchestrator` with servers/key |
| AC2 partial observation modes | F1-F4 | `tests/test_agents/test_observe.py` |
| AC3 real NL channel | G2, G4, G7, G8 | `test_real_nl_channel_delivers_message_to_opponent_next_observation`, envelope test |
| AC4 hybrid veto | D5-D9, I4, I5 | `tests/test_agents/test_agent.py` |
| AC5 belief logged/scored | F1, G6, G8 | `test_belief_and_belief_error_recorded` |
| AC6 no network in tests + 3x3 | B4-B5, G8, I6, J1 | `test_no_network_no_key_full_fake_series` |
| AC7 backward compatibility | D3, G1-G3, J2, J3 | existing mover/orchestrator/strategy tests |
| AC8 config/no hard-code/no secrets | A1-A2, E3, I7 | config tests + static guards |
| AC9 LLM telemetry | B3, F3, F5, G5, H2 | telemetry tests + summary fields |
| AC10 prompt caching | C2, C6, B2 | prompt cache test + Anthropic call assembly test |
| Doctrine hook: liar raises belief error | B4, I1 | `test_liar_persona_increases_belief_error` |
| Doctrine hook: reasoning private | G4, G6, I2 | `test_reasoning_private_message_public` |
| Doctrine hook: confidence regime | D7, I3 | `test_confidence_weighted_veto_regime` |

## Definition of Done
- [ ] Every box above is ticked and its Check passed.
- [ ] All PRD acceptance criteria hold (`PRD_step5_nl_integration.md` ֲ§7).
- [x] No real API call happens in tests; `FakeLLM` covers all automated agent tests.
- [x] No secrets are committed; `ANTHROPIC_API_KEY` is read only by the real SDK from the environment.
- [x] `src/mcp_servers/` remains free of LLM code/imports.
- [x] Existing tests still pass through `MoverAgent` compatibility.
- [ ] Manual live run is recorded in Developer notes if a key/server environment is available.
