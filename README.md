# HW6 — Dual AI Agent Race via MCP Servers (Cop & Thief)

A pursuit–evasion game in which **two autonomous AI agents** — a **Cop** and a **Thief** —
play on a resizable grid by **talking to each other in free natural language**. Each agent
lives behind its **own MCP server** (Model Context Protocol, FastMCP v3); a referee
orchestrator owns ground truth and routes the agents' messages. The graded value of this
project is the **orchestration and multi-agent architecture**, not the game algorithm.

> Course: *Dual AI Agent Conversation via MCP Servers* (Dr. Yoram Segal). Assignment §13, Table 4.

## What it does

- Two **separate FastMCP servers** (Cop on `:8001`, Thief on `:8002`) expose validation tools.
- A **referee orchestrator** holds the authoritative `GameState`, applies moves through the
  pure engine, and acts as the **message bus** between the two agents.
- Each agent's move is chosen by a **hybrid brain**: an LLM (Claude) proposes a move, a
  message, and a belief about the opponent's location; a **minimax** strategy vetoes only
  illegal or blunder moves. The agents **deceive each other in natural language**.
- Every ply is logged to a **JSONL replay**, replayable in a **web GUI** (FastAPI + `<canvas>`).
- The MCP servers are **deployed to Google Cloud Run** behind per-server bearer tokens.
- After a 6-sub-game series the result is emailed as a **JSON report via the Gmail API**.

## The 8 build steps

| # | Step | Package | Status |
|---|------|---------|--------|
| 1 | Game logic & rules | `src/game/` | ✅ |
| 2 | MCP infrastructure (2 FastMCP servers) | `src/mcp_servers/` | ✅ |
| 3 | Full local run (orchestrator + message bus) | `src/orchestrator/` | ✅ |
| 4 | Decision engine (minimax / Q-table / greedy) | `src/strategy/` | ✅ |
| 5 | Natural-language integration (graded core) | `src/agents/` | ✅ |
| 6 | Graphical user interface (replay) | `src/gui/` | ✅ |
| 7 | Cloud distributed deployment | `Dockerfile`, `deploy/` | ✅ |
| 8 | Gmail API reporting | `src/reporting/` | ✅ |

## Fixed game parameters (`config.yaml`, no hard-coding)

| Key | Default | Meaning |
|-----|---------|---------|
| `grid_size` | `[5, 5]` | board dimensions (resizable: 2×2 → 5×5 tested) |
| `max_moves` | `25` | plies per sub-game |
| `num_games` | `6` | sub-games per series (roles swap each game) |
| `max_barriers` | `5` | barriers the Cop may place |
| `scoring` | `20 / 10 / 5 / 5` | cop_win / thief_win / cop_loss / thief_loss |

## Quickstart

```bash
uv sync                                  # install deps (uv-managed)
uv run pytest -q                         # 180 tests pass

# Local run: start the two MCP servers in two terminals, then the orchestrator
uv run python -m src.mcp_servers.cop_server      # terminal 1  -> :8001
uv run python -m src.mcp_servers.thief_server    # terminal 2  -> :8002
uv run python -m src.orchestrator                # terminal 3  -> plays a 6-game series

# Replay GUI
uv run python -m src.gui                         # http://127.0.0.1:8000
```

## Formal model — Decentralized POMDP (Dec-POMDP)

The game is a finite-horizon **Dec-POMDP**, the standard model for cooperative-style
multi-agent decision making under partial observability. Here the two agents are
**adversarial**, so it is a competitive Dec-POMDP (a partially observable stochastic game):

```
M = ⟨ I, S, {A_i}, T, R, {Ω_i}, O, h ⟩
```

| Symbol | In this project |
|--------|-----------------|
| **I** — agents | `{ Cop, Thief }` |
| **S** — state | `(cop_pos, thief_pos, barriers ⊆ cells, to_move, moves_used)` — held authoritatively by the referee, never by a server |
| **A_i** — actions | 8 directional moves `{N,S,E,W,NE,NW,SE,SW}` for both; the **Cop** additionally has `PLACE_BARRIER` (on its own cell). Illegal moves are filtered by the engine. |
| **T** — transition | **deterministic**: the Thief moves first, then the Cop; `apply_move` updates `S`. Barriers block both agents and cost the Cop a turn. |
| **R** — reward | terminal scoring: capture (same cell) ⇒ Cop `+20`, Thief `+5`; survival to `max_moves` ⇒ Thief `+10`, Cop `+5`. |
| **Ω_i** — observation | per-agent view, **config-selectable**: `blind` (no opponent position — messages are the *only* sensor), `noisy` (reveal radius + quadrant hint), `full` (perfect). Default `noisy`. |
| **O** — observation fn | `recorders.observe(state, side)` projects `S` to `Ω_i` under the configured mode, emitting stable `sees_opponent` / `opponent_pos` fields. |
| **h** — horizon | `max_moves = 25` plies per sub-game; `num_games = 6` per series with role-swap. |

**Communication as action.** Beyond the physical action `A_i`, each agent emits a
**free-text message** every turn — a *cheap-talk* / communication action. Under `blind`
observation the message channel is the agent's **only** information about the opponent, which
is exactly what makes "infer the opponent's location and deceive" a real Dec-POMDP problem
rather than a solved game. Each agent also maintains an explicit **belief** `b_i` (its guess
of the opponent's cell); we score belief accuracy as the Chebyshev error between the guessed
and true position (`belief_error`).

## Architecture

Strict tier separation — the LLM lives **only** in the client tier; the MCP servers are
stateless validators; the referee owns all ground truth.

```
                      ┌──────────────────────────────────────────────┐
                      │  Referee / Orchestrator  (src/orchestrator)   │
                      │  • authoritative GameState  • message bus     │
                      │  • applies moves via pure engine (src/game)   │
                      │  • recorders: JSONL replay, telemetry, fog    │
                      └───────┬───────────────────────────┬──────────┘
            Agent A (Cop)     │ HTTP + Bearer             │ HTTP + Bearer    Agent B (Thief)
   ┌──────────────────────┐   │                           │   ┌──────────────────────┐
   │ LLMAgent (src/agents)│   │                           │   │ LLMAgent (src/agents)│
   │ • Claude proposes    │   ▼                           ▼   │ • Claude proposes    │
   │   move+msg+belief    │ ┌─────────────────┐  ┌─────────────────┐ move+msg+belief   │
   │ • minimax veto       │ │  Cop MCP server │  │ Thief MCP server│ • minimax veto    │
   │   (src/strategy)     │ │ (FastMCP :8001) │  │ (FastMCP :8002) │   (src/strategy)  │
   └──────────────────────┘ │ validate-only   │  │ validate-only   └──────────────────┘
                            │ place_barrier ✓ │  │ (no barrier)    │
                            └─────────────────┘  └─────────────────┘
                                    ▲                     ▲
                                    └─── deployed to Google Cloud Run ───┘

   Replay JSONL ──► GUI (src/gui, FastAPI + canvas)      Series result ──► Gmail report (src/reporting)
```

**Tiers**

- **`src/game/`** — pure engine: grid, 8-dir movement, barriers, capture, scoring, series
  loop. No MCP, no LLM, fully unit-tested. Single source of rules.
- **`src/mcp_servers/`** — two FastMCP servers exposing `ping` / `validate_location` /
  `validate_move` / `send_message` (+ `place_barrier` validate on the Cop only — a tested
  **asymmetry**). **Stateless**: they validate, the referee applies.
- **`src/orchestrator/`** — referee loop, `ServerGateway` protocol (`HttpGateway` for prod,
  `InMemoryGateway` for port-free tests), message bus, and recorders (replay/telemetry/fog).
- **`src/strategy/`** — `MinimaxMover` (alpha-beta, clone-safe), `QTableMover` (offline-trained,
  committed table), `GreedyMover`; config-selectable per role.
- **`src/agents/`** — `LLMAgent` hybrid (Claude proposes, minimax vetoes) with an injectable
  `LLMClient` (`AnthropicLLM` real / `FakeLLM` deterministic in tests).
- **`src/gui/`** — FastAPI replay viewer; all data shaping in unit-tested Python, JS is a
  dumb renderer.
- **`src/reporting/`** — Gmail-API JSON report builder + fail-soft send hook.
