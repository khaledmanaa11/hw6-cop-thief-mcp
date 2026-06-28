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

## Architecture-challenge analysis

The interesting engineering problems this design had to solve:

1. **Who owns state?** MCP tools are naturally request/response and stateless. If each server
   held its own copy of the board the two copies would drift. **Resolution:** the referee owns
   the single authoritative `GameState`; servers only *validate*. This makes the system
   restart-safe and the servers horizontally trivial to deploy.

2. **Partial observability vs. a shared board.** A Dec-POMDP needs each agent to see only its
   own observation `Ω_i`, but the engine knows everything. **Resolution:** an explicit
   observation function (`recorders.observe`) projects the full state down to per-agent fog
   (`blind`/`noisy`/`full`), so an agent literally cannot read the opponent's coordinates
   except through messages.

3. **Natural language as a control channel.** Free text is unbounded and adversarial — agents
   lie. **Resolution:** structured LLM output `{move, message, belief, confidence, intent,
   reasoning}` where only `message` is ever transmitted and `reasoning` is **private**
   (logged, never enveloped). The verbal trash-talk is grading-safe *by construction*: the
   visible channel carries no reliable information.

4. **LLM unreliability vs. legal play.** A raw LLM will occasionally pick an illegal or losing
   move. **Resolution:** the **hybrid veto** — minimax checks the LLM's proposal and overrides
   only illegal/blunder moves, weighted by the LLM's stated confidence. The LLM is genuinely
   part of the choice, but the game stays legal.

5. **Reproducibility of a non-deterministic LLM.** **Resolution:** record-and-replay. Real LLM
   I/O is written to JSONL; determinism is guaranteed in tests via `FakeLLM`. The same JSONL
   spine feeds the GUI (Step 6) and the email report (Step 8).

6. **Secrets across a cloud boundary.** **Resolution:** per-server static bearer tokens read
   from env (`COP_AUTH_TOKEN` / `THIEF_AUTH_TOKEN`), distinct per role to preserve the
   cop/thief asymmetry, **active only when the env var is set** so local runs and the 180 tests
   stay green. No token, URL, or key is ever committed.

## Proof of correct agent communication

A real series played **against the live Cloud Run servers**
(`runs/20260628T150334.jsonl`, 91 plies, 6 sub-games). Each turn carries the agent's natural-
language message, its private intent, and its belief about the opponent (Chebyshev error):

```
T1 THIEF  move=N   intent=deceive  guess=[1,1] err=1
   "Well, well. Northwest, you say? How quaint. I'm heading that way myself…"
T2 COP    move=E   intent=bait     guess=[0,3] err=3
   "Northwest? NORTHWEST?! Kid, I own this board. Every wall, every corner…"
T3 THIEF  move=S   intent=bait     guess=[3,0] err=3
   "East? Oh, you're EAST now? That's funny. A second ago you owned the whole board…"
T4 COP    move=SE  intent=bait     guess=[2,3] err=2
   "Oh, you're *worried* now — asking about rows, about my position. That's fear talking…"
```

**Series-level evidence the channel works:**

- **Intents over 91 turns:** `deceive 45 · bait 37 · probe 5 · trap 3 · truth 1` — the agents
  overwhelmingly choose to mislead, exactly as the Dec-POMDP incentive predicts.
- **Belief accuracy:** average Chebyshev `belief_error = 1.05` (max 4) — despite both sides
  lying, each agent infers the opponent's location to within ~1 cell from the message stream.
- **Outcome:** 5 Cop captures + 1 Thief escape (sub-game 4 ran the full 25 plies) — consistent
  with the empirical finding that the default 5×5 board is Cop-favored.
- **Telemetry:** 91 LLM calls, ~117k input / ~33k output tokens, ~6 s/call.

The orchestrator also renders an **ASCII board** each ply (`render_board`) and a readable
transcript; the GUI (`src/gui`) replays the same JSONL with the board, the conversation log,
per-agent fog, and the belief ghosts.

## Cloud Deployment

The two MCP servers are containerized as **one image** (role selected by `MCP_ROLE=cop|thief`)
and deployed live to **Google Cloud Run** (project `hw6-copthief`, region `us-central1`). The
LLM and orchestrator stay client-side; only the tool-servers go to the cloud.

**Live public endpoints:**

| Server | URL |
|--------|-----|
| Cop | `https://hw6-cop-bp45yo7zda-uc.a.run.app/mcp` |
| Thief | `https://hw6-thief-bp45yo7zda-uc.a.run.app/mcp` |

**Auth — per-server static bearer token (401 without, accepted with):**

```bash
# No token → rejected
$ curl -i https://hw6-cop-bp45yo7zda-uc.a.run.app/mcp
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer error="invalid_token"

# Valid token → request reaches the MCP server (NOT 401)
$ curl -i -H "Authorization: Bearer <COP_TOKEN>" https://hw6-cop-bp45yo7zda-uc.a.run.app/mcp
HTTP/1.1 406 Not Acceptable          # 406 only because bare curl lacks the
mcp-session-id: <…>                  # text/event-stream Accept header — the point is
                                     # it is NOT 401, so the token was accepted.
```

Distinct `COP_AUTH_TOKEN` / `THIEF_AUTH_TOKEN` values are set as Cloud Run env vars and
**never committed** (shown here only as `<COP_TOKEN>`). To point the orchestrator at the cloud,
set `COP_SERVER_URL` / `THIEF_SERVER_URL` and the matching tokens in `.env`
(see `.env.example`); `gateway_from_env` falls back to local config when they are absent.

Build & deploy steps are in `docs/step7_cloud_deploy/DEPLOY.md` (`gcloud builds submit` +
`gcloud run deploy`, no local Docker required).

## Email reporting (Gmail API)

After a 6-sub-game series the orchestrator can email a **JSON-only report** to the lecturer
(`rmisegal+uoh26b@gmail.com`) via the **Gmail API v1** using OAuth2 user consent (scope
`gmail.send` only).

**One-time login, then automatic send:**

```bash
# 1. One-time browser consent — stores a refresh token under secrets/ (gitignored)
uv run python -m src.reporting auth

# 2. Enable the hook (config.yaml: report.enabled: true, or REPORT_ENABLED=true)
#    The next series automatically emails the JSON report on completion.
uv run python -m src.orchestrator
```

The report body is compact JSON: run header (grid size, num games, scoring, per-side agent
type and observation mode), per-sub-game results, group totals, a telemetry summary, and the
replay-log filename — no attachment, no inline JSONL.

**Safety / cyber-hygiene:** the hook is **fail-soft** (`maybe_send_report` never raises into
the orchestrator) and **disabled by default** (`report.enabled: false` + absent token ⇒ dev
runs never email anyone and the 180 tests stay green). OAuth client secrets and the refresh
token live only under `secrets/` (gitignored, alongside `gmail_credentials.json` /
`gmail_token.json`); the scope is minimal and no secret is ever written to the body or logs.
