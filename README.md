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
